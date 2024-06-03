from contextlib import contextmanager
from typing import ContextManager

import redis


class RedisClient:
    def __init__(self, host: str, port: int, max_connections: int = 10):
        self._host: str = host
        self._port: int = port
        self._max_connections: int = max_connections

        # Initialize connection pool
        self.connection_pool: redis.ConnectionPool = redis.ConnectionPool(
            host=self._host,
            port=self._port,
            max_connections=self._max_connections,
            decode_responses=True
        )

    @contextmanager
    def connection(self) -> ContextManager[redis.Redis]:
        r: redis.Redis = redis.Redis(connection_pool=self.connection_pool)
        try:
            yield r
        finally:
            r.close()


class AbstractRedisClientFactory:
    def create(self) -> RedisClient:
        raise NotImplementedError


class ClothoDockerRedisClientFactory(AbstractRedisClientFactory):
    def create(self) -> RedisClient:
        return RedisClient(
            host="redis",
            port=6379
        )


class LocalRedisClientFactory(AbstractRedisClientFactory):
    def create(self) -> RedisClient:
        return RedisClient(
            host="localhost",
            port=6379
        )


if __name__ == '__main__':
    # Test on local redis server
    redis_factory: AbstractRedisClientFactory = LocalRedisClientFactory()
    redis_client: RedisClient = redis_factory.create()

    with redis_client.connection() as r:
        r: redis.Redis
        r.set('foo', 'bar')
        print(r.get('foo'))

        # Delete the key
        r.delete('foo')
        print(r.get('foo'))
