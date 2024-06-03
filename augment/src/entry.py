from commons.models.augmenters import AbstractAugmenter, RandomAugmenter
from commons.models.denoisers import AbstractDenoiser, LowPassDenosier
from commons.models.fits_interfaces import LinuxFitsInterface, LocalTestingFitsInterface, AbstractFitsInterface
from commons.models.mask_generators import AbstractMaskGenerator, CircleMaskGenerator
from commons.models.radon_transformers import RadonTransformer
from commons.orchestration.pipeline import Pipeline, BackendPipelineShutdownCallback, DummyPipelineShutdownCallback, AbstractPipelineShutdownCallback
from commons.utils.sql_utils import ClothoDockerPostgresClientFactory, LocalPostgresClientFactory, AbstractPostgresClientFactory
from constants import CONTAINER_ID, CONTAINER_PORT, CONTAINER_MODE
from script import AugmentScript

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

    augmenter: AbstractAugmenter = RandomAugmenter()
    mask_generator: AbstractMaskGenerator = CircleMaskGenerator()
    radon_transformer: RadonTransformer = RadonTransformer(mask_generator)
    denoiser: AbstractDenoiser = LowPassDenosier()

    script = AugmentScript(postgres_factory, fits_interface, augmenter, radon_transformer, mask_generator, denoiser)
    pipeline = Pipeline(CONTAINER_ID, CONTAINER_PORT, script, shutdown_callback)
    pipeline.start()
