from enum import Enum
from typing import List

STARTING_PORT_NUMBER = 6500


class InfrastructureType(Enum):
    ARCHITECTURE: str = "architecture"
    PIPELINE: str = "pipeline"


class ContainerTypeDefinition:
    def __init__(self, name: str, description: str, image_tag: str, infrastructure_type: InfrastructureType):
        self.name: str = name
        self.description: str = description
        self.image_tag: str = image_tag
        self.infrastructure_type: InfrastructureType = infrastructure_type

    def is_pipeline(self) -> bool:
        return self.infrastructure_type == InfrastructureType.PIPELINE


class ContainerType(Enum):
    AUGMENT = "augment"
    BACKEND = "backend"
    FETCH = "fetch"
    FRONTEND = "frontend"
    RADON = "radon"

    @staticmethod
    def is_valid_container_type(container_type: str) -> bool:
        return any(container_type == item.value for item in ContainerType)

    def is_pipeline(self) -> bool:
        return self in {ContainerType.AUGMENT, ContainerType.FETCH, ContainerType.RADON}

    @staticmethod
    def is_valid_pipeline_type(container_type: str) -> bool:
        return ContainerType.is_valid_container_type(container_type) and ContainerType(container_type).is_pipeline()

    def get_image_tag(self) -> str:
        if self.is_pipeline():
            return f"pipeline-{self.value}"
        return self.value

    @staticmethod
    def get_pipeline_types() -> List["ContainerType"]:
        return [ContainerType.AUGMENT, ContainerType.FETCH, ContainerType.RADON]
