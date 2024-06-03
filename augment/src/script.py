import sys
from typing import Any, Dict, Tuple, Optional, List

import numpy as np
from psycopg2 import extensions
from tqdm import tqdm

from commons.models.augmenters import AbstractAugmenter, AugmentResult
from commons.models.denoisers import AbstractDenoiser
from commons.models.fits_interfaces import AbstractFitsInterface, GalaxyFitsData
from commons.models.mask_generators import AbstractMaskGenerator
from commons.models.radon_transformers import RadonTransformer
from commons.models.running_error import RunningErrorCalculator
from commons.orchestration.pipeline import AbstractScript
from commons.utils.parallel_utils import run_in_parallel
from commons.utils.sql_utils import AbstractPostgresClientFactory, PostgresClient
from constants import THREAD_COUNT, MAX_RUNNING_ERROR_COUNT, AUGMENTATION_COUNT


class AugmentScript(AbstractScript):
    def __init__(self, postgres_factory: AbstractPostgresClientFactory,
                 fits_interface: AbstractFitsInterface,
                 augmenter: AbstractAugmenter,
                 radon_transformer: RadonTransformer,
                 mask_generator: AbstractMaskGenerator,
                 denoiser: AbstractDenoiser):
        super().__init__()

        self.postgres_client: PostgresClient = postgres_factory.create()
        self.fits_interface: AbstractFitsInterface = fits_interface
        self.augmenter: AbstractAugmenter = augmenter
        self.radon_transformer: RadonTransformer = radon_transformer
        self.mask_generator: AbstractMaskGenerator = mask_generator
        self.denoiser: AbstractDenoiser = denoiser

    def run_batch(self):
        print(f"Starting iteration #{self.iteration}...")

        # Query and lock a batch of galaxies
        with self.postgres_client.cursor() as cursor:
            cursor.execute(f"""
                SELECT r.source_id, g.bin_id, r.band, r.total_error, r.running_count
                FROM rotations AS r
                    JOIN galaxies AS g ON r.source_id = g.source_id
                    JOIN bands AS b ON r.source_id = b.source_id AND r.band = b.band
                WHERE r.running_count < {MAX_RUNNING_ERROR_COUNT}
                    AND b.error_count = 0
                LIMIT {THREAD_COUNT}
                FOR UPDATE SKIP LOCKED
            """)
            metadata_list = cursor.fetchall()

        # If we've completed processing of all fetched galaxies, stop loop
        if not metadata_list:
            print("No more galaxies to process, stopping script!")
            self.schedule_stop()
            return

        # Process in parallel with THREAD_COUNT threads
        pbar = tqdm(metadata_list, desc=f"Iteration #{self.iteration}", total=len(metadata_list))
        process_results = run_in_parallel(self.parallel_process, [[*metadata[:3]] for metadata in metadata_list],
                                          THREAD_COUNT, lambda: pbar.update(1))
        pbar.close()

        # Insert results into database
        with self.postgres_client.cursor() as cursor:
            successful, failed = 0, 0
            for metadata, process_result in zip(metadata_list, process_results):
                error_calculator, is_error = process_result
                if not is_error:
                    self.insert_result(cursor, metadata[0], metadata[2], error_calculator)
                    successful += 1
                else:
                    self.insert_error(cursor, metadata[0], metadata[2])
                    failed += 1

        print(f"Processed {successful} galaxies successfully, {failed} failed, total {len(metadata_list)} galaxies")

    def parallel_process(self, source_id: str, bin_id: str, band: str) -> Tuple[Optional[RunningErrorCalculator], bool]:
        """ Processes a single galaxy band, can be run in parallel """
        try:
            # Load FITS data
            band_fits_data_container: GalaxyFitsData = self.fits_interface.load_fits(source_id, bin_id)
            if band_fits_data_container is None or band_fits_data_container.get_band_data(band) is None:
                raise Exception(f"FITS data for {bin_id}/{source_id} band {band} is invalid, unable to load & preprocess")
            band_fits_array: np.ndarray = band_fits_data_container.get_band_data(band).mask(self.mask_generator).denoise(self.denoiser).build()

            # Calculate "oracle" rotation
            ideal_rotation: float = self.radon_transformer.transform(band_fits_array).get_rotation()

            # Generate augmentations & estimate error
            augmentations: List[AugmentResult] = self.augmenter.random_augment(band_fits_array, count=AUGMENTATION_COUNT)
            running_error_calculator: RunningErrorCalculator = RunningErrorCalculator()

            for augment_result in augmentations:
                augment_result: AugmentResult
                actual_rotation: float = self.radon_transformer.transform(augment_result.result_image).get_rotation()
                running_error_calculator.update(int(ideal_rotation + augment_result.angle_delta), int(actual_rotation))

            return running_error_calculator, False
        except Exception as e:
            print(f"Error processing source_id={source_id}, bin_id={bin_id}, band={band}", file=sys.stderr)
            print(e, file=sys.stderr)

            # Set error flag
            return None, True

    @staticmethod
    def insert_result(cursor: extensions.cursor, source_id: str, band: str, error: RunningErrorCalculator) -> None:
        cursor.execute("""
            UPDATE rotations
            SET total_error = total_error + %s,
                running_count = running_count + %s
            WHERE source_id = %s AND band = %s
        """, (error.total_error, error.running_count, source_id, band))

    @staticmethod
    def insert_error(cursor: extensions.cursor, source_id: str, band: str) -> None:
        cursor.execute("""
            UPDATE bands
            SET error_count = error_count + 1
            WHERE source_id = %s AND band = %s
        """, (source_id, band))

    def update_batch_status(self):
        # Do nothing
        pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "iteration_progress": 0,
            "iteration_max_progress": THREAD_COUNT
        }
