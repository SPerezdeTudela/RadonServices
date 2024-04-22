import sys
from typing import Dict, Any, List, Optional

import numpy as np
from psycopg2 import extensions

from commons.constants.fits_constants import FITS_BANDS
from commons.models.denoisers import AbstractDenoiser
from commons.models.fits_interfaces import AbstractFitsInterface, GalaxyFitsData, BandFitsBuilder
from commons.models.mask_generators import AbstractMaskGenerator
from commons.models.radon_transformers import RadonTransformer, RadonTransformResult
from commons.orchestration.pipeline import AbstractScript
from commons.utils.sql_utils import AbstractPostgresClientFactory, PostgresClient
from constants import SQL_BATCH_SIZE
from models import GalaxyRadonTransformResult


class RadonScript(AbstractScript):
    def __init__(self, postgres_factory: AbstractPostgresClientFactory,
                 fits_interface: AbstractFitsInterface,
                 radon_transformer: RadonTransformer,
                 mask_generator: AbstractMaskGenerator,
                 denoiser: AbstractDenoiser):
        super().__init__()

        self.postgres_client: PostgresClient = postgres_factory.create()
        self.fits_interface: AbstractFitsInterface = fits_interface
        self.radon_transformer: RadonTransformer = radon_transformer
        self.mask_generator: AbstractMaskGenerator = mask_generator
        self.denoiser: AbstractDenoiser = denoiser

        self.iteration_progress: int = 0

    def run_batch(self):
        print(f"Starting iteration #{self.iteration}...")
        self.iteration_progress = 0

        with self.postgres_client.cursor() as cursor:
            cursor: extensions.cursor
            cursor.execute(f"""
                SELECT source_id, bin_id FROM galaxies
                WHERE status='Fetched'
                ORDER BY id LIMIT {SQL_BATCH_SIZE} FOR UPDATE SKIP LOCKED
            """)
            metadata = cursor.fetchall()

            # If we've completed processing of all fetched galaxies, stop script
            if not metadata:
                print("No more galaxies to process, stopping radon script")
                self.schedule_stop()
                return

            # Process galaxies sequentially
            result_rows: List[GalaxyRadonTransformResult] = []
            for source_id, bin_id in metadata:
                try:
                    process_result: GalaxyRadonTransformResult = self.process_galaxy(source_id, bin_id)
                except Exception as e:
                    print(f"ERROR: Failed to process galaxy b{bin_id}/{source_id}", file=sys.stderr)
                    print(e, file=sys.stderr)
                    process_result = GalaxyRadonTransformResult.error(source_id, bin_id)

                result_rows.append(process_result)
                self.iteration_progress += 1

            # Update results to the database
            for result in result_rows:
                result: GalaxyRadonTransformResult
                self.update_sql_database(cursor, result)

        error_count = len([result for result in result_rows if result.is_error])
        print(f"Iteration #{self.iteration} completed with {error_count}/{SQL_BATCH_SIZE} errors")

    def process_galaxy(self, source_id: str, bin_id: int) -> GalaxyRadonTransformResult:
        galaxy_data: GalaxyFitsData = self.fits_interface.load_fits(source_id, str(bin_id))

        radon_results: Dict[str, Optional[RadonTransformResult]] = {}
        is_error = True
        for band in FITS_BANDS:
            band_fits_builder: Optional[BandFitsBuilder] = galaxy_data.get_band_data(band)
            if band_fits_builder is None:
                print(f"ERROR: Band {band} has invalid data for galaxy {source_id} bin {bin_id}", file=sys.stderr)
                radon_results[band] = None
                continue

            band_fits_data: np.ndarray = band_fits_builder.mask(self.mask_generator).denoise(self.denoiser).build()
            radon_result: RadonTransformResult = self.radon_transformer.transform(band_fits_data)
            radon_results[band] = radon_result
            is_error = False

        return GalaxyRadonTransformResult(source_id, bin_id, radon_results, is_error)

    @staticmethod
    def update_sql_database(cursor: extensions.cursor, result: GalaxyRadonTransformResult):
        """ Inserts result into the rotations table and updates status for the galaxies table """
        for band, radon_result in result.band_results.items():
            band: str
            radon_result: Optional[RadonTransformResult]

            # Update bands table
            error_delta: int = 1 if radon_result is None else 0
            cursor.execute(
                """
                INSERT INTO bands (source_id, band, error_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_id, band)
                DO UPDATE SET error_count = bands.error_count + EXCLUDED.error_count;
                """,
                (result.source_id, band, error_delta)
            )

            # Insert rotation into rotations table
            rotation: float = radon_result.get_rotation() if radon_result is not None else -1
            cursor.execute(
                """
                INSERT INTO rotations (source_id, band, degree)
                VALUES (%s, %s, %s)
                ON CONFLICT (source_id, band)
                DO UPDATE SET degree = EXCLUDED.degree;
                """,
                (result.source_id, band, rotation)
            )

        # Update galaxies table's status
        cursor.execute(
            """
            UPDATE galaxies
            SET status = 'Processed'
            WHERE source_id = %s AND bin_id = %s;
            """,
            (result.source_id, result.bin_id)
        )

    def update_batch_status(self):
        pass

    def get_status(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "iteration_progress": self.iteration_progress,
            "iteration_max_progress": SQL_BATCH_SIZE
        }
