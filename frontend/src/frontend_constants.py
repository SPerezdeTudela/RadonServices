import os
from typing import Dict

CONTAINER_MODE: str = os.getenv("CONTAINER_MODE", "development")
print(f"Configured environment variable CONTAINER_MODE as {CONTAINER_MODE}")

PIPELINE_DESCRIPTIONS: Dict[str, str] = {
    "fetch": "Fetches galaxies from the database and saves them as FITS files",
    "radon": "Applies the Radon transform to calculate the position-angle of galaxies",
    "augment": "Estimates radon pipeline's errors by augmenting the galaxies"
}
