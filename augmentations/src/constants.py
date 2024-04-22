import os

##################
# Container Configurations (must be present)
CONTAINER_ID = os.getenv("CONTAINER_ID")
assert CONTAINER_ID is not None, "Environment variable CONTAINER_ID must be set"
print(f"Configured environment variable CONTAINER_ID as '{CONTAINER_ID}'")

CONTAINER_PORT = int(os.getenv("CONTAINER_PORT"))
assert CONTAINER_PORT is not None, "Environment variable PORT must be set"
print(f"Configured environment variable PORT as {CONTAINER_PORT}")

CONTAINER_MODE: str = os.getenv("CONTAINER_MODE", "development")
print(f"Configured environment variable CONTAINER_MODE as {CONTAINER_MODE}")

##################
# Pipeline Configurations

# Number of augmentations to generate per galaxy
AUGMENTATION_COUNT = int(os.getenv("AUGMENTATION_COUNT", 100))
print(f"Configured environment variable AUGMENTATION_COUNT as {AUGMENTATION_COUNT}")

# Number of threads to use for parallel processing
THREAD_COUNT = int(os.getenv("THREAD_COUNT", 64))
print(f"Configured environment variable THREAD_COUNT as {THREAD_COUNT}")

# Maximum number of running errors to calculate for each galaxy
MAX_RUNNING_ERROR_COUNT = int(os.getenv("MAX_RUNNING_ERROR_COUNT", 100))
assert MAX_RUNNING_ERROR_COUNT > 0 and MAX_RUNNING_ERROR_COUNT % AUGMENTATION_COUNT == 0, \
    f"MAX_RUNNING_ERROR_COUNT {MAX_RUNNING_ERROR_COUNT} must be a multiple of AUGMENTATION_COUNT {AUGMENTATION_COUNT}"
print(f"Configured environment variable MAX_RUNNING_ERROR_COUNT as {MAX_RUNNING_ERROR_COUNT}")
