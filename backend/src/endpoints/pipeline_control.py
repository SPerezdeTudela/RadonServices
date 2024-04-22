import traceback
from typing import Any, Dict, List

import requests
from docker.types import Mount
from flask import make_response, request
from flask_restful import Api, Resource

import commons.utils.log_util as log
from commons.constants.pipeline_constants import VALID_PIPELINE_TYPES
from src.docker_interface import boot_container_until_success, add_pseudo_container
from src.endpoints.wrappers import safe_request
from src.shared_states import PIPELINE_CONTAINERS, get_container_by_id, get_container_address


class PipelineEndpoint(Resource):
    path: str = "/pipelines/<pipeline_type>"

    @staticmethod
    def bind_self(api: Api):
        api.add_resource(PipelineEndpoint, PipelineEndpoint.path)

    @safe_request
    def get(self, pipeline_type: str, uid: str):
        """
        Gets the status of the active pipelines, allowing for an optional pipeline type
        - if no type is specified, it will retrieve the status of all pipelines
        """
        if pipeline_type == "all":
            pipeline_json: Dict[str, Any] = {}
            for pipeline_type, containers in PIPELINE_CONTAINERS.items():
                pipeline_json[pipeline_type] = []
                for container in containers:
                    hostname = container.container.attrs["Config"]["Hostname"]
                    pipeline_json[pipeline_type].append({
                        "id": container.container_id,
                        "name": container.container.name,
                        "hostname": hostname,
                        "port": container.port,
                        "status": container.container.attrs["State"]["Status"]
                    })
            return make_response({"message": "OK", "pipelines": pipeline_json}, 200)

        # Check if pipeline type is valid
        valid_pipeline_types: List[str] = ["fetch", "radon"]
        pipeline_type: str = pipeline_type.lower()
        if pipeline_type not in valid_pipeline_types:
            return make_response({
                "error": f"Invalid pipeline type {pipeline_type}!",
                "valid_types": valid_pipeline_types
            }, 400)

        # Get the list of containers of the corresponding pipeline type
        container_metadata: List[Dict[str, Any]] = []
        for container in PIPELINE_CONTAINERS[f"pipeline-{pipeline_type}"]:
            hostname: str = container.container.attrs["Config"]["Hostname"]
            container_metadata.append({
                "id": container.container_id,
                "name": container.container.name,
                "hostname": hostname,
                "port": container.port,
                "status": container.container.attrs["State"]["Status"]
            })

        return make_response({"message": "OK", "containers": container_metadata}, 200)

    @safe_request
    def post(self, pipeline_type, uid):
        """
        Creates a new pipeline of the corresponding pipeline type
        """
        # Check if pipeline type is valid
        pipeline_type = pipeline_type.lower()
        if pipeline_type == "pseudo":
            add_pseudo_container("pipeline-fetch", "pseudo-container-id", 5578)
            return make_response({"message": "OK", "new_pipeline": "fetch", "ports": 5578}, 200)

        if pipeline_type not in VALID_PIPELINE_TYPES:
            return make_response({
                "error": f"Invalid pipeline type {pipeline_type}!",
                "valid_types": VALID_PIPELINE_TYPES
            }, 400)

        pipeline_config: Dict[str, Any] = request.get_json()
        image_repository: str = pipeline_config["image_repository"]
        image_tag: str = pipeline_config["image_tag"]
        log.request(uid, f"Creating a new '{pipeline_type}' pipeline using image '{image_repository}:{image_tag}'...")

        environment_vars: Dict[str, Any] = {}
        for key, value in pipeline_config.items():
            if key.startswith("env"):
                environment_vars[key.replace("env_", "").upper()] = value
        log.request(uid, f"Set environment variables: {environment_vars}")

        fits_volume: Mount = Mount(target="/fits-data", source=pipeline_config["fits_volume_path"], type="bind")
        new_ports = boot_container_until_success(
            repository=image_repository,
            image_tag=image_tag,
            environment={
                # Note: port & container ID information will be automatically added
            },
            mounts=[fits_volume],
            network="radonservices_radon_network"  # note the 'radonservices' prefix because compose adds that
        )

        return make_response({
            "message": "OK",
            "new_pipeline": pipeline_type,
            "ports": new_ports
        }, 200)

    @safe_request
    def delete(self, pipeline_type: str, uid: str):
        """ Gracefully shuts down the pipeline of the corresponding type """
        # Check if pipeline type is valid
        pipeline_type: str = pipeline_type.lower()
        if pipeline_type not in VALID_PIPELINE_TYPES:
            return make_response({
                "error": f"Invalid pipeline type {pipeline_type}!",
                "valid_types": VALID_PIPELINE_TYPES
            }, 400)

        container_id: str = request.get_json()["container_id"]

        # Build URL to send to the pipeline
        container = get_container_by_id(container_id)
        if container is None:
            return make_response({"error": f"Container with ID {container_id} does not exist!"}, 404)

        log.request(uid, f"Terminating the '{pipeline_type}' pipeline with container ID {container_id}...")
        container_url: str = f"{get_container_address(container_id)}/control"
        try:
            log.request(uid, f"Sending stop request to '{container_url}'...")
            requests.post(container_url, json={"action": "stop"})
        except Exception as e:
            log.error(f"Failed to send stop request to '{container_url}': {e}")
            return make_response({
                "error": f"Container with ID {container_id} is not running!",
                "details": traceback.format_exc()
            }, 404)

        return make_response({"message": "OK"}, 200)
