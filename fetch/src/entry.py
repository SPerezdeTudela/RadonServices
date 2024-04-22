from commons.models.fits_interfaces import LinuxFitsInterface, AbstractFitsInterface, LocalTestingFitsInterface
from commons.orchestration.pipeline import Pipeline, BackendPipelineShutdownCallback, AbstractPipelineShutdownCallback, DummyPipelineShutdownCallback
from commons.utils.sql_utils import ClothoDockerPostgresClientFactory, AbstractPostgresClientFactory, LocalPostgresClientFactory
from constants import CONTAINER_ID, CONTAINER_PORT, CONTAINER_MODE
from script import FetchScript

if __name__ == "__main__":
    # This file is the Docker container's entrypoint
    print(f"Running in {CONTAINER_MODE} mode")

    if CONTAINER_MODE == "production":
        # Use clotho-based interfaces
        postgres_factory: AbstractPostgresClientFactory = ClothoDockerPostgresClientFactory()
        fits_interface: AbstractFitsInterface = LinuxFitsInterface()
        shutdown_callback: AbstractPipelineShutdownCallback = BackendPipelineShutdownCallback()
    else:
        # Use local/testing interfaces
        postgres_factory: AbstractPostgresClientFactory = LocalPostgresClientFactory()
        fits_interface: AbstractFitsInterface = LocalTestingFitsInterface()
        shutdown_callback: AbstractPipelineShutdownCallback = DummyPipelineShutdownCallback()

    script = FetchScript(postgres_factory, fits_interface)
    pipeline = Pipeline(CONTAINER_ID, CONTAINER_PORT, script, shutdown_callback)
    pipeline.start()
