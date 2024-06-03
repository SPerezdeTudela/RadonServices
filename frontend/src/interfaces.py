from commons.utils.sql_utils import AbstractPostgresClientFactory, PostgresClient, ClothoDockerPostgresClientFactory, LocalPostgresClientFactory
from src.constants import CONTAINER_MODE

# Postgres client initialization
if CONTAINER_MODE == "production":
    postgres_factory: AbstractPostgresClientFactory = ClothoDockerPostgresClientFactory()
else:
    postgres_factory: AbstractPostgresClientFactory = LocalPostgresClientFactory()
postgres_client: PostgresClient = postgres_factory.create()


def get_postgres_client() -> PostgresClient:
    return postgres_client


# Orchestrator integration
def get_orchestrator_url() -> str:
    if CONTAINER_MODE == "production":
        return "http://orchestrator:5000"
    return "http://localhost:5000"
