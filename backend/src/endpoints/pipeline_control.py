import traceback
from typing import Any, Dict, List, Optional

import requests
from docker.types import Mount
from flask import make_response, request
from flask_restful import Api, Resource

import commons.utils.log_util as log
from commons.constants.pipeline_constants import ContainerType
from src.shared_states import redis_interface
from src.docker_interface import boot_container_until_success, PipelineContainer
from src.endpoints.wrappers import safe_request


class PipelineEndpoint(Resource):
    path: str = "/pipelines/<pipeline_type>"

    @staticmethod
    def bind_self(api: Api):
        api.add_resource(PipelineEndpoint, PipelineEndpoint.path)

    @safe_request
    def get(self, pipeline_type: str, uid: str):
        """ Gets the status of the active pipelines by type """
        # Check if pipeline type is valid
        pipeline_type: str = pipeline_type.lower()
        if not ContainerType.is_valid_pipeline_type(pipeline_type):
            log.request(uid, f"Received invalid pipeline type '{pipeline_type}'")
            return make_response({
                "error": f"Invalid pipeline type {pipeline_type}!",
                "valid_types": [enum_choice.value for enum_choice in ContainerType]
            }, 400)

        # Get the list of containers of the corresponding pipeline type
        container_type: ContainerType = ContainerType(pipeline_type)
        container_metadata: List[Dict[str, Any]] = []
        for container_id in redis_interface.get_container_ids_by_type(container_type):
            container: Optional[PipelineContainer] = redis_interface.get_container_by_id(container_id)
            if container is None or container.container is None:
                log.error(f"Failed to retrieve container '{container_id}'")
                continue

            container_metadata.append({
                "id": container_id,
                "name": container.container.name,
                "hostname": container.get_url(),
                "port": container.port,
                "status": container.get_status()
            })

        return make_response({"message": "OK", "containers": container_metadata}, 200)

    @safe_request
    def post(self, pipeline_type: str, uid: str):
        """ Creates a new pipeline of the corresponding pipeline type """
        # Check if pipeline type is valid
        pipeline_type: str = pipeline_type.lower()
        if not ContainerType.is_valid_pipeline_type(pipeline_type):
            log.request(uid, f"Received invalid pipeline type '{pipeline_type}'")
            return make_response({
                "error": f"Invalid pipeline type {pipeline_type}!",
                "valid_types": [enum_choice.value for enum_choice in ContainerType]
            }, 400)

        pipeline_config: Dict[str, Any] = request.get_json()
        image_repository: str = pipeline_config["image_repository"]
        container_type: ContainerType = ContainerType(pipeline_type)
        log.request(uid, f"Creating a new '{container_type}' pipeline using repository '{image_repository}'...")

        environment_vars: Dict[str, Any] = {}
        for key, value in pipeline_config.items():
            if key.startswith("env"):
                environment_vars[key.replace("env_", "").upper()] = value
        log.request(uid, f"Set environment variables: {environment_vars}")

        fits_volume: Mount = Mount(target="/fits-data", source=pipeline_config["fits_volume_path"], type="bind")
        new_ports = boot_container_until_success(
            container_type=container_type,
            control_port=redis_interface.get_next_port(),
            repository=image_repository,
            environment={
                # Note: port & container ID information will be automatically added
                "CONTAINER_MODE": "production",
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
        if not ContainerType.is_valid_pipeline_type(pipeline_type):
            log.request(uid, f"Received invalid pipeline type '{pipeline_type}'")
            return make_response({
                "error": f"Invalid pipeline type {pipeline_type}!",
                "valid_types": [enum_choice.value for enum_choice in ContainerType]
            }, 400)

        container_id: str = request.get_json()["container_id"]
        container_type: ContainerType = ContainerType(pipeline_type)

        # Build URL to send to the pipeline
        container: Optional[PipelineContainer] = redis_interface.get_container_by_id(container_id)
        if container is None or container.container is None:
            return make_response({"error": f"Failed to retrieve container '{container_id}'"}, 404)

        log.request(uid, f"Terminating the '{container_type}' pipeline with container ID {container_id}...")
        container_url: str = f"{container.get_url()}/control"
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
