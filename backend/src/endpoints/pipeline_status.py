from typing import Any, Dict, Optional

import requests
from flask import make_response, request
from flask_restful import Resource
from requests import Response

import commons.utils.log_util as log
from src.endpoints.wrappers import safe_request
from src.shared_states import redis_interface, PipelineContainer

# In-memory cache for pipeline status
CONTAINER_STATUS: Dict[str, Any] = {}


class PipelineStatusEndpoint(Resource):
    path = "/pipelines/status/<container_id>"

    @staticmethod
    def bind_self(api):
        api.add_resource(PipelineStatusEndpoint, PipelineStatusEndpoint.path)

    @safe_request
    def get(self, container_id: str, uid: str):
        container: Optional[PipelineContainer] = redis_interface.get_container_by_id(container_id)
        if container is None:
            log.request(uid, f"Container '{container_id}' not found!")
            return make_response({
                "error": f"Container '{container_id}' not found!",
            }, 404)

        container_url: str = f"{container.get_url()}/status"
        log.request(uid, f"Fetching status from container '{container_url}'")
        try:
            response: Response = requests.get(container_url, timeout=3)
        except Exception as e:
            log.error(f"Failed to fetch status from container '{container_url}': {e}")
            return make_response({
                "error": f"Failed to fetch status from container '{container_id}'",
            }, 404)

        json: Dict[str, Any] = response.json()
        return make_response({"message": "OK", "status": json["status"]}, 200)

    @safe_request
    def post(self, container_id: str, uid: str):
        """ Updates the status of the current pipeline """
        new_status: Dict[str, Any] = request.get_json()
        CONTAINER_STATUS[container_id]: Dict[str, Any] = new_status

        log.request(uid, f"Updated status for container '{container_id}': {new_status}")
        return make_response({"message": "OK"}, 200)

    @safe_request
    def delete(self, container_id: str, uid: str):
        """ Indicates that the pipeline is stopped, called by the pipeline itself """
        container: Optional[PipelineContainer] = redis_interface.get_container_by_id(container_id)
        if container is None:
            log.request(uid, f"Container '{container_id}' not found!")
            return make_response({
                "error": f"Container '{container_id}' not found!",
            }, 404)

        log.request(uid, f"Deleting container '{container_id}'")
        redis_interface.delete_container_by_id(container)

        # Remove the container status from the cache
        del CONTAINER_STATUS[container_id]

        return make_response({"message": "OK"}, 200)
