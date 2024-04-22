import atexit
import traceback
import uuid
from threading import Thread
from typing import Dict, List, Optional

import docker
from docker.errors import APIError
from docker.types import Mount

import commons.utils.log_util as log
from src.shared_states import DynamicContainer, PIPELINE_CONTAINERS

# Starting port for each type of containers
# - this will be incremented for each container booted
# - matches the image tag (e.g. pipeline-radon)
pipeline_ports = {
    "pipeline-fetch": 6500,
    "pipeline-radon": 6600,
    "pipeline-augment": 6700,
}

# List of used ports
ports = []

# Mapping of { port => docker container object }
# - used when backend shuts down to shut down all dynamic containers
port_container_map: Dict[int, docker.models.containers.Container] = {}

# Flag to ignore the liveliness check
# - should only be set once, and that is upon _teardown() is called
is_shutting_down = False

# Docker client object
DOCKER_CLIENT = docker.from_env()


def add_pseudo_container(image_tag: str, container_id: str, port: int):
    """ Adds an already-booted container to the list of containers. Only used in testing """
    global pipeline_ports, ports, port_container_map

    class FakeContainer:
        def __init__(self, container_id: str, name: str, hostname: str, port: int, status: str):
            self.container = self

            self.id = container_id
            self.name = name
            self.hostname = hostname
            self.port = port
            self.status = status
            self.attrs = {
                "Config": {"Hostname": hostname},
                "State": {"Status": status}
            }

    fake_container = FakeContainer(container_id, f"fake-{container_id}", "localhost", port, "fake")
    new_container: DynamicContainer = DynamicContainer(fake_container, container_id, image_tag, port)
    PIPELINE_CONTAINERS[image_tag].append(new_container)

    # Save port/shutdown info
    ports.append(port)
    port_container_map[port] = new_container


def boot_container_until_success(image_tag: str, count: int = 1, repository: str = "dockerneoc/radon",
                                 entrypoint: str = "python ./src/entry.py",
                                 environment: Optional[Dict[str, any]] = None,
                                 mounts: Optional[List[Mount]] = None,
                                 network: Optional[str] = None,
                                 max_fails: int = 3):
    """
    Attempts to boot the container until it is successful
    - if not successful, it will increment 'host_port' and try again
    - if it fails 'max_fails' times, it will raise an error

    Args:
        image_tag (str): container's Docker tag (e.g. pipeline-radon), also serves as the pipeline type identifier
        count (int): number of containers needed
        repository (str): Docker repository to pull from
        entrypoint (str): entrypoint command to run
        environment (dict): environment variables to pass to the container
        mounts (list): list of mounts (e.g. volumes) to attach to the container
        network (str): network to attach the container to
        max_fails (int): max number of boot failures before raising an error
    """
    global pipeline_ports, ports, port_container_map

    success = 0
    fails = 0
    new_ports = []
    while success < count and fails < max_fails:
        try:
            # Get port to use for this container type
            new_port = pipeline_ports[image_tag]

            # Add extra information to environment variable
            if environment is None:
                environment = {}
            environment["CONTAINER_PORT"] = new_port

            container_id = str(uuid.uuid4())
            environment["CONTAINER_ID"] = container_id

            # Pull the image from the repository
            thread: Thread = Thread(target=_pull_image, args=(repository, image_tag))
            thread.start()

            print("Waiting for image to be pulled", end="")
            seconds_waited = 0
            while thread.is_alive():
                if seconds_waited > 30:
                    print("Error")
                    print("Timed out while waiting for image to be pulled!")
                    break

                print(".", end="")
                seconds_waited += 1

            print("Done!")

            # Attempts to boot the container at the port
            new_container_object = DOCKER_CLIENT.containers.run(
                image=f"{repository}:{image_tag}",
                environment=environment,
                mounts=mounts,
                network=network,
                detach=True,
                # auto_remove=True
            )

            # Successful boot! save container info
            new_container = DynamicContainer(new_container_object, container_id, image_tag, new_port)
            PIPELINE_CONTAINERS[image_tag].append(new_container)

            # Save port/shutdown info
            ports.append(new_port)
            port_container_map[new_port] = new_container

            new_ports.append(new_port)

            log.info(f"Successfully loaded '{image_tag}' container at port {new_port}!")
            success += 1
        except Exception as e:
            log.error(f"Encountered exception while booting '{image_tag}' container")
            log.error(f"{e}")
            log.error(f"{traceback.format_exc()}")
            fails += 1

        pipeline_ports[image_tag] += 1

    if fails == max_fails:
        raise APIError(f"Unable to boot '{image_tag}' container(s), failed {max_fails} times!")

    log.info(f"Successfully booted {count} containers for tag '{image_tag}'!")
    return new_ports


def _pull_image(repository: str, image_tag: str):
    log.info(f"Pulling '{repository}:{image_tag}' from Docker Hub...")
    DOCKER_CLIENT.images.pull(repository, image_tag)
    log.info(f"Successfully pulled '{repository}:{image_tag}' from Docker Hub!")


def _teardown():
    """ This will be called automatically whenever the flask server is shutting down """
    global is_shutting_down

    log.info("Shutting down all containers...")
    is_shutting_down = True

    for port, container in port_container_map.items():
        try:
            container.stop()
            log.info(f"Successfully shut down the container at port {port}")
        except APIError as e:
            log.error(f"Failed to shut down the container at port {port}!")
            log.error(f"{e}")
            log.error(f"{traceback.format_exc()}")

    log.info("Successfully shut down all containers!")


# Register shutdown hook
atexit.register(_teardown)

# def initialize():
#     """ Boots all containers for each treatment group """
#     log.info(f"Initializing containers for {len(TREATMENT_MAPPING)} treatment groups...")
#
#     # Boot containers for each treatment group
#     for group, group_data in TREATMENT_MAPPING.items():
#         docker_tag, ratio, count = group_data
#         boot_container_until_success(docker_tag, count, group)
#         log.info(f"Successfully booted {count} containers for treatment group '{group}'!")
#
#     # Setup liveliness ping
#     def periodic():
#         while not is_shutting_down:
#             log.debug("Executing liveliness ping...")
#             liveliness_ping()
#             time.sleep(PING_DELAY)
#
#     log.info("Setting up periodic liveliness ping...")
#     thread = Thread(target=periodic, daemon=True)
#     thread.start()


# def liveliness_ping():
#     """ Called to ping ALL the containers and restart/remove if needed """
#     for group, group_ports in treatment_port_mapping.items():
#         to_remove = []
#         for port in group_ports[:]:
#             log.debug(f"Pinging group '{group}' port {port}...")
#             container = containers_mapping[port]
#             try:
#                 response = requests.get(url=f"http://localhost:{port}/status")
#                 if response.status_code == 200:
#                     log.debug(f"[{group}] Successfully reached the container at port {port}")
#                 # Go to exception handling block if response is not 200
#                 else:
#                     log.error(f"[{group}] Status check for the container at {port} returned status {response.status_code}!")
#                     raise requests.exceptions.RequestException()
#             except requests.exceptions.RequestException:
#                 log.warning(f"[{group}] Shutting down unhealthy container port {port}...")
#                 try:
#                     container.remove(force=True)
#                     log.error(f"[{group}] Successfully removed container at {port}")
#                 except APIError:
#                     log.error(f"[{group}] Failed to force remove container at {port}!")
#
#                 # Remove container registration
#                 ports.remove(port)
#                 del containers_mapping[port]
#                 to_remove.append(port)  # avoid concurrent modification
#
#                 # Create new container at new port
#                 log.info(f"[{group}] Loading a new container at port {host_port}...")
#                 containers_mapping[host_port] = boot_container_until_success(TREATMENT_MAPPING[group][0], 1, group)
#                 log.info(f"[{group}] Successfully loaded replacement container at port {host_port}!")
#
#         # Remove all "dead" ports
#         for port in to_remove:
#             treatment_port_mapping[group].remove(port)
