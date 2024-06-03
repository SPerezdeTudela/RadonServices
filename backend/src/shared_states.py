from typing import Optional, Set

import redis

from commons.constants.pipeline_constants import ContainerType, STARTING_PORT_NUMBER
from commons.utils.redis_utils import RedisClient, AbstractRedisClientFactory, ClothoDockerRedisClientFactory, LocalRedisClientFactory
from docker_interface import PipelineContainer
from constants import CONTAINER_MODE


class RedisKey:
    @staticmethod
    def container_by_id_key(container_id: str) -> str:
        return f"container-id:str:{container_id}"

    @staticmethod
    def container_set_by_type_key(container_type: ContainerType) -> str:
        return f"container-type:set:{container_type.value}"

    @staticmethod
    def current_port_key() -> str:
        return "current-port:int"


class RedisInterface:
    def __init__(self, redis_client: RedisClient):
        self.redis_client: RedisClient = redis_client

    def get_container_by_id(self, container_id: str) -> Optional[PipelineContainer]:
        with self.redis_client.connection() as r:
            r: redis.Redis
            data: str = r.get(RedisKey.container_by_id_key(container_id))

        if data is None:
            return None
        return PipelineContainer.deserialize(data)

    def create_container_by_id(self, container: PipelineContainer):
        """ Creates a new container in the cache, updating both the container data entry and the container type set """
        container_key: str = RedisKey.container_by_id_key(container.container_id)
        container_type_key: str = RedisKey.container_set_by_type_key(container.pipeline_type)

        with self.redis_client.connection() as r:
            r: redis.Redis
            # Set the container data
            r.set(container_key, container.serialize())
            # Add the container ID to the container type set
            r.sadd(container_type_key, container.container_id)

    def delete_container_by_id(self, container: PipelineContainer):
        """ Deletes a container from the cache, removing from both the container data entry and the container type set """
        container_key: str = RedisKey.container_by_id_key(container.container_id)
        container_type_key: str = RedisKey.container_set_by_type_key(container.pipeline_type)

        with self.redis_client.connection() as r:
            r: redis.Redis
            # Delete the container data
            r.delete(container_key)
            # Remove the container ID from the container type set
            r.srem(container_type_key, container.container_id)

    def get_container_ids_by_type(self, container_type: ContainerType) -> Set[str]:
        with self.redis_client.connection() as r:
            r: redis.Redis
            container_ids: Set[str] = r.smembers(RedisKey.container_set_by_type_key(container_type))
        return container_ids

    def get_next_port(self) -> int:
        with self.redis_client.connection() as r:
            r: redis.Redis
            return r.incr(RedisKey.current_port_key(), amount=STARTING_PORT_NUMBER)


def create_redis_interface(production: bool = True) -> RedisInterface:
    client_factory: AbstractRedisClientFactory = ClothoDockerRedisClientFactory() if production else LocalRedisClientFactory()
    return RedisInterface(client_factory.create())


# Initialize the Redis interface
redis_interface: RedisInterface = create_redis_interface(CONTAINER_MODE == "production")
