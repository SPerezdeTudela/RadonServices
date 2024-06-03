import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, Optional, List

from constants import ContainerType


class PackageAppearance:
    def __init__(self, package: str):
        self.package: str = package

        # Map of { path: version }
        self.appearances: Dict[str, str] = {}

    def add_appearance(self, path: str, version: str):
        self.appearances[path] = version

    def has_multiple_appearances(self) -> bool:
        return len(self.appearances) > 1


class RequirementsSchema:
    def __init__(self, requirements_yml_path: str):
        # Dynamic imports to avoid importing before PyYAML is installed
        import yaml

        with open(requirements_yml_path, "r") as f:
            self.requirements: Dict[str, Any] = yaml.safe_load(f).get("requirements", {})

    def validate(self) -> bool:
        """
        Validates the requirements schema, checking:
        1. requirements structure is correct (error)
        2. there are no duplicate keys across all requirements (warning)
        3. compares specified versions to the latest versions on PyPI (warning)
        """
        valid: bool = True

        # Check requirements structure & duplicate keys
        package_appearances: Dict[str, PackageAppearance] = {}
        paths: List[str] = self.get_all_paths()
        for path in paths:
            try:
                requirements = self.get_path(path)
                for key, value in requirements.items():
                    if key not in package_appearances:
                        package_appearances[key] = PackageAppearance(key)
                    package_appearances[key].add_appearance(path, value)
            except Exception as e:
                print(f"Error: {e}", file=sys.stderr)
                valid = False

        # Print warnings for duplicate keys
        for package, appearances in package_appearances.items():
            if appearances.has_multiple_appearances():
                paths: List[str] = list(appearances.appearances.keys())
                print(f"Warning: Package '{package}' appears in multiple paths: {', '.join(paths)}", file=sys.stderr)

        # 3. Check for latest versions
        for package, appearances in package_appearances.items():
            time.sleep(0.2)  # Rate limit to prevent overloading PyPI servers
            latest_version: Optional[str] = self.get_latest_version_from_pypi(package)
            if latest_version is None:
                continue

            for path, version in appearances.appearances.items():
                if version != latest_version:
                    print(f"Warning: Package '{package}:{version}' at path '{path}' has a newer version available on PyPI: {latest_version}", file=sys.stderr)

        return valid

    @staticmethod
    def get_all_paths() -> List[str]:
        """ Returns a list of all paths in the requirements file """
        paths: List[str] = ["common", "pipelines.common"]
        for container_type in ContainerType:
            if container_type.is_pipeline():
                paths.append(f"pipelines.{container_type.value}")
            else:
                paths.append(container_type.value)
        return paths

    def get_path(self, path: str) -> Dict[str, str]:
        """ Returns the requirements at the given path, use dot to indicate nested keys """
        keys = path.split(".")
        requirements = self.requirements
        for key in keys:
            requirements = requirements.get(key, {})

        if requirements is not None and not isinstance(requirements, list):
            raise ValueError(f"Requirements at path '{path}' is a '{type(requirements)}', expected list or None (empty list)")

        if requirements is None:
            requirements = []

        # Convert list of dictionaries to a single dictionary
        requirements_dict: Dict[str, str] = {}
        for requirement in requirements:
            requirements_dict.update(requirement)

        return requirements_dict

    def get_all_requirements(self) -> Dict[str, str]:
        all_requirements: Dict[str, str] = {}
        paths: List[str] = self.get_all_paths()
        for path in paths:
            requirements = self.get_path(path)
            all_requirements.update(requirements)

        return all_requirements

    def get_requirements(self, container_type: ContainerType) -> Dict[str, str]:
        requirements: Dict[str, str] = self.get_path("common")

        # If the container type is a pipeline, add pipeline-specific requirements
        if container_type.is_pipeline():
            pipeline_commons: Dict[str, str] = self.get_path("pipelines.common")
            requirements.update(pipeline_commons)

            pipeline_specific: Dict[str, str] = self.get_path(f"pipelines.{container_type.value}")
            requirements.update(pipeline_specific)
        else:
            container_specific: Dict[str, str] = self.get_path(f"{container_type.value}")
            requirements.update(container_specific)

        return requirements

    @staticmethod
    def get_latest_version_from_pypi(package: str) -> Optional[str]:
        url: str = f"https://pypi.org/pypi/{package}/json"
        try:
            with urllib.request.urlopen(url) as response:
                package_info = json.loads(response.read())
            return package_info["info"]["version"]
        except Exception as e:
            print(f"Failed to fetch PyPI version for package '{package}': {e}", file=sys.stderr)
            return None


if __name__ == "__main__":
    os.chdir("..")
    project_root: str = os.getcwd()
    container_type: ContainerType = ContainerType.FETCH
    requirements_schema: RequirementsSchema = RequirementsSchema(os.path.join(project_root, "commons", "requirements.yml"))
    requirements_schema.validate()
