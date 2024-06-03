import json
import traceback
import uuid
from typing import Dict, List, Optional, Any

import docker
from docker.models.containers import Container
from docker.types import Mount

import commons.utils.log_util as log
from commons.constants.pipeline_constants import ContainerType

# Docker client object
DOCKER_CLIENT: docker.DockerClient = docker.from_env()


class PipelineContainer:
    """ Represents a created pipeline container """

    def __init__(self, container_id: str, pipeline_type: ContainerType, control_port: int):
        self.container_id: str = container_id
        self.pipeline_type: ContainerType = pipeline_type
        self.port: int = control_port

        self.container: Optional[Container] = None
        try:
            self.container: Optional[Container] = DOCKER_CLIENT.containers.get(container_id)
        except Exception as e:
            log.error(f"Failed to retrieve container with ID {container_id}: {e}")

    @staticmethod
    def deserialize(json_string: str) -> "PipelineContainer":
        json_object: Dict[str, str] = json.loads(json_string)
        try:
            container_id: str = json_object["container_id"]
            pipeline_type: ContainerType = ContainerType(json_object["pipeline_type"])
            port: int = int(json_object["port"])
        except Exception as e:
            raise ValueError(f"Failed to deserialize PipelineContainer: {e}")

        return PipelineContainer(container_id, pipeline_type, port)

    def serialize(self) -> str:
        return json.dumps({
            "container_id": self.container_id,
            "pipeline_type": self.pipeline_type.value,
            "port": self.port
        })

    def __str__(self) -> str:
        return f"PipelineContainer({self.container_id}, {self.pipeline_type}, {self.port})"

    def get_status(self) -> str:
        if self.container is None:
            raise ValueError("Unable to retrieve status of a non-existent container")
        return self.container.status

    def get_url(self) -> str:
        """ Returns the Docker URL of the container, only accessible within the Docker network """
        if self.container is None:
            raise ValueError("Unable to retrieve URL of a non-existent container")

        ip: str = self.container.attrs["Config"]["Hostname"]
        return f"http://{ip}:{self.port}"


def boot_container_until_success(container_type: ContainerType, control_port: int, repository: str, environment: Optional[Dict[str, Any]] = None,
                                 mounts: Optional[List[Mount]] = None, network: Optional[str] = None, entry_override: Optional[str] = None, auto_remove: bool = False) \
        -> Optional[PipelineContainer]:
    """
    Attempts to boot the container, should be run in a separate thread

    Args:
        container_type (ContainerType): type of container to boot
        control_port (int): port to boot the container at
        repository (str): Docker repository to pull from
        environment (dict): environment variables to pass to the container
        mounts (list): list of mounts (e.g. volumes) to attach to the container
        network (str): network to attach the container to
        entry_override (str): entry command override
        auto_remove (bool): whether to remove the container upon shutdown
    """
    try:
        # Add extra information to environment variable
        if environment is None:
            environment: Dict[str, Any] = {}

        container_id: str = str(uuid.uuid4())
        environment["CONTAINER_ID"]: str = container_id
        environment["CONTAINER_PORT"]: int = control_port

        # Pull the image from the repository
        image_tag: str = container_type.get_image_tag()
        log.info(f"Pulling '{repository}:{image_tag}' from Docker Hub...")
        DOCKER_CLIENT.images.pull(repository, image_tag)
        log.info(f"Successfully pulled '{repository}:{image_tag}' from Docker Hub!")

        # Attempts to boot the container at the port
        DOCKER_CLIENT.containers.run(
            image=f"{repository}:{image_tag}",
            environment=environment,
            mounts=mounts,
            network=network,
            entrypoint=entry_override,
            auto_remove=auto_remove,
            detach=True
        )

        # Successful boot, save container info
        log.info(f"Successfully booted '{image_tag}' container at port {control_port}!")
        return PipelineContainer(container_id, container_type, control_port)
    except Exception as e:
        log.error(f"Encountered exception while booting '{container_type.value}' container")
        log.error(f"{e}")
        log.error(f"{traceback.format_exc()}")
        return None
