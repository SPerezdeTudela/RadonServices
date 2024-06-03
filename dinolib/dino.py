import argparse
import os
import shutil
import subprocess
import sys
import venv
from typing import Dict, List, Tuple, Callable, Any

from constants import ContainerType
from requirements_parser import RequirementsSchema


def setup_workspace(project_root: str, force: bool = False):
    print(f"Setting up workspace at {project_root}")

    # Create venv
    venv_path: str = os.path.join(project_root, "venv")
    venv_exists: bool = os.path.exists(venv_path)
    if not venv_exists or force:
        if venv_exists:
            print(f"Force flag is set, recreating virtual environment")
            print(f"Removing existing virtual environment at '{venv_path}'")
            shutil.rmtree(venv_path)

        venv.create(venv_path, with_pip=True)
        print(f"Created virtual environment at '{venv_path}'")
    else:
        print(f"Virtual environment already exists at '{venv_path}', skipping creation")

    # Activate venv
    if os.name == "nt":
        # Windows
        activate_script: str = os.path.join(venv_path, "Scripts", "activate")
        activate_formatter: Callable[[str], str] = lambda script: f"{script} with .bat (cmd) or .ps1 (powershell) "
    else:
        # Unix
        activate_script: str = os.path.join(venv_path, "bin", "activate")
        activate_formatter: Callable[[str], str] = lambda script: f"source {script}"

    if not os.path.isfile(activate_script):
        print(f"Activation script not found at: {activate_script}", file=sys.stderr)
        print("Please activate the virtual environment manually", file=sys.stderr)
        return

    print(f"Activation script found: {activate_script}")

    print(f"Run the following command to activate the virtual environment:")
    print(f"> {activate_formatter(activate_script)}")


def install_dependencies(project_root: str):
    # Install PyYAML first to parse requirements.yml
    try:
        print(f"Installing PyYAML to parse requirements... ", end="", flush=True)
        subprocess.run(["pip", "install", "PyYAML"], capture_output=True, check=True)
        print("done")
    except subprocess.CalledProcessError as e:
        print("failed")
        print(f"Failed to install PyYAML: {e}", file=sys.stderr)
        print(e.stderr.decode("utf-8"), file=sys.stderr)
        print(e.stdout.decode("utf-8"), file=sys.stdout)
        raise e

    print(f"Parsing dependencies for the entire project...")
    requirements_schema: RequirementsSchema = RequirementsSchema(os.path.join(project_root, "commons", "requirements.yml"))

    all_requirements: List[Tuple[str, str]] = sorted(requirements_schema.get_all_requirements().items(), key=lambda x: x[0].lower())
    requirements_count: int = len(all_requirements)
    print(f"Installing dependencies ({requirements_count}): {', '.join(f'{package}=={version}' for package, version in all_requirements)}")

    failed: List[Tuple[str, str]] = []
    for i, (package, version) in enumerate(all_requirements):
        try:
            print(f"- [{i + 1}/{requirements_count}] Installing {package}:{version}... ", end="", flush=True)
            subprocess.run(["pip", "install", f"{package}=={version}"], capture_output=True, check=True)
            print("done")
        except subprocess.CalledProcessError as e:
            print("failed")
            print(f"- [{i + 1}/{requirements_count}] Failed to install {package}:{version} - {e}")
            print(e.stderr.decode("utf-8"), file=sys.stderr)
            print(e.stdout.decode("utf-8"), file=sys.stdout)
            failed.append((package, version))

    if failed:
        print(f"Failed to install {len(failed)} package(s): {', '.join(f'{package}=={version}' for package, version in failed)}", file=sys.stderr)
        raise Exception("Failed to install dependencies")

    print("All dependencies installed successfully")


class FileManipulator:
    def __init__(self, project_root: str):
        self.project_root: str = project_root
        self.requirements_schema: RequirementsSchema = RequirementsSchema(os.path.join(self.project_root, "commons", "requirements.yml"))

    def copy_commons(self, container_type: ContainerType):
        """ Copies the common files to the pipeline directory """
        commons_directory: str = os.path.join(self.project_root, "commons")
        destination_directory: str = os.path.join(self.project_root, container_type.value, "src", "commons")
        print(f"Copying commons from {commons_directory} to {destination_directory}")

        if not os.path.exists(commons_directory):
            raise FileNotFoundError("Commons directory not found")

        # Remove old directory if it exists
        if os.path.exists(destination_directory):
            print(f"Removing existing directory {destination_directory}")
            self.cleanup_commons(container_type)

        # Copy over the commons directory
        shutil.copytree(commons_directory, destination_directory)

    def cleanup_commons(self, container_type: ContainerType):
        """ Removes the common files from the pipeline directory """
        destination_directory: str = os.path.join(self.project_root, container_type.value, "src", "commons")
        if not os.path.exists(destination_directory):
            return

        print(f"Cleaning up directory {destination_directory}")
        shutil.rmtree(destination_directory)

    def write_requirements(self, container_type: ContainerType) -> None:
        print(f"Compiling requirements for '{container_type.value}' container")
        if not self.requirements_schema.validate():
            raise ValueError("Requirements schema is invalid")

        container_requirements: Dict[str, str] = self.requirements_schema.get_requirements(container_type)
        container_requirements_list: List[Tuple[str, str]] = sorted(container_requirements.items(), key=lambda x: x[0].lower())
        print(f"Compiled requirements: {', '.join(f'{package}=={version}' for package, version in container_requirements_list)}")

        requirements_path: str = self.get_requirements_file_path(container_type)
        print(f"Writing requirements to file: {requirements_path}")
        with open(requirements_path, "w") as f:
            for package, version in container_requirements_list:
                f.write(f"{package}=={version}\n")

    def cleanup_requirements(self, container_type: ContainerType) -> None:
        requirements_path: str = self.get_requirements_file_path(container_type)
        if os.path.exists(requirements_path):
            print(f"Cleaning up requirements file: {requirements_path}")
            os.remove(requirements_path)

    def get_requirements_file_path(self, container_type: ContainerType) -> str:
        return os.path.join(self.project_root, container_type.value, "dino_generated_requirements.txt")


class Dino:
    def __init__(self, project_root: str):
        self.project_root: str = project_root
        self.file_manipulator: FileManipulator = FileManipulator(self.project_root)

    def build_image(self, container_type: ContainerType, repository: str) -> None:
        # Prepare pipeline directory
        print(f"Preparing directory for '{container_type.value}' container")
        self.file_manipulator.write_requirements(container_type)
        self.file_manipulator.copy_commons(container_type)

        # Build image
        print(f"Building '{container_type.value}' image, this may take a while")
        container_path: str = os.path.join(self.project_root, container_type.value)
        container_full_tag: str = f"{repository}:{container_type.get_image_tag()}"
        try:
            subprocess.run(["docker", "build", "--no-cache", "-t", container_full_tag, "."], cwd=container_path, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Encountered exception when building image: {e}", file=sys.stderr)
        except KeyboardInterrupt:
            print("Build process was interrupted", file=sys.stderr)

        # Cleanup pipeline directory
        print(f"Cleaning up directory for '{container_type.value}' container")
        self.file_manipulator.cleanup_requirements(container_type)
        self.file_manipulator.cleanup_commons(container_type)

    def push_image(self, container_type: ContainerType, repository: str) -> None:
        print(f"Pushing '{container_type.value}' image to Docker Hub")
        container_path: str = os.path.join(self.project_root, container_type.value)
        try:
            subprocess.run(["docker", "push", f"{repository}:{container_type.get_image_tag()}"], cwd=container_path, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Encountered exception when pushing image: {e}", file=sys.stderr)


if __name__ == "__main__":
    """
    Dino commands:
    - setup: Sets up the workspace virtual environment, returns a command to activate it
    - install: Installs dependencies from requirements.yml
    - build --image <container_type> --repository <repository> [--upload | -u]: Build and optionally push the image to docker hub
    - clean: Cleans up the workspace, removing the venv and any other temporary files
    """

    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Build and manage Docker images")

    # Optional arguments
    parser.add_argument("--cwd", help="Override the current working directory")

    # Add sub-commands
    subparsers: Any = parser.add_subparsers(title="sub-commands", dest="subcommand")

    # Sub-command: setup
    setup_parser: argparse.ArgumentParser = subparsers.add_parser("setup", help="Setup the project's virtual environment")
    setup_parser.add_argument("-f", "--force", action="store_true", help="Always recreate the virtual environment")

    # Sub-command: install
    install_parser: argparse.ArgumentParser = subparsers.add_parser("install", help="Install dependencies from requirements.yml, requires venv")

    # Sub-command: build
    build_parser: argparse.ArgumentParser = subparsers.add_parser("build", help="Build a Docker image for the specified container, requires venv & libraries")
    build_parser.add_argument("-i", "--image", required=True, choices=[container.value for container in ContainerType], help="Container type to build")
    build_parser.add_argument("-r", "--repository", required=True, help="Docker repository for tagging the built image")
    build_parser.add_argument("-u", "--upload", action="store_true", help="Upload to Docker Hub")

    # Parse arguments
    args: argparse.Namespace = parser.parse_args()
    print("Debugging arguments:", args)

    # Change working directory if specified (usually when invoked directly via the command line)
    if args.cwd:
        print(f"Set working directory to {args.cwd}")
        os.chdir(args.cwd)
    project_root: str = os.getcwd()

    # Handle subcommands
    subcommand: str = args.subcommand
    if subcommand is None:
        print("No build operation specified, use --help for more information", file=sys.stderr)
        sys.exit(1)

    # Basic commands (using all built-in functions)
    if subcommand == "setup":
        setup_workspace(project_root, force=bool(args.force))
        sys.exit(0)
    elif subcommand == "install":
        install_dependencies(project_root)
        sys.exit(0)

    # Initialize Dino
    try:
        dino: Dino = Dino(project_root)
    except ModuleNotFoundError as e:
        print(f"Failed to import Dino dependencies: {e}", file=sys.stderr)
        print("Please run 'setup' and 'install' commands first", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to initialize Dino: {e}", file=sys.stderr)
        sys.exit(1)

    # Advanced commands (requires venv & PyYAML)
    if subcommand == "build":
        container_type: ContainerType = ContainerType(args.image)
        dino.build_image(container_type, args.repository)
        print(f"Completed building image for '{container_type.value}' container")

        if args.upload:
            dino.push_image(container_type, args.repository)
            print(f"Image for '{container_type.value}' container successfully pushed to Docker Hub")
    elif subcommand == "clean":
        pass
    else:
        print(f"Unknown command '{args.command}'", file=sys.stderr)
        sys.exit(1)
