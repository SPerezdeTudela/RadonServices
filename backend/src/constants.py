import os

CONTAINER_MODE: str = os.getenv("CONTAINER_MODE", "development")
print(f"Configured environment variable CONTAINER_MODE as {CONTAINER_MODE}")
