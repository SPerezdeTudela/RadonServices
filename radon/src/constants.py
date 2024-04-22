import os

##################
# Container Configurations
CONTAINER_ID: str = os.getenv("CONTAINER_ID")
assert CONTAINER_ID is not None, "Environment variable CONTAINER_ID must be set"
print(f"Configured environment variable CONTAINER_ID as '{CONTAINER_ID}'")

CONTAINER_PORT: int = int(os.getenv("CONTAINER_PORT"))
assert CONTAINER_PORT is not None, "Environment variable PORT must be set"
print(f"Configured environment variable PORT as {CONTAINER_PORT}")

CONTAINER_MODE: str = os.getenv("CONTAINER_MODE", "development")
print(f"Configured environment variable CONTAINER_MODE as {CONTAINER_MODE}")

##################
# Pipeline Configurations
SQL_BATCH_SIZE: int = int(os.getenv("SQL_BATCH_SIZE", 200))
print(f"Configured environment variable SQL_BATCH_SIZE as {SQL_BATCH_SIZE}")
