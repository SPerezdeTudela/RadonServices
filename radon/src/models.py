from typing import Dict, Optional

from commons.constants.fits_constants import FITS_BANDS
from commons.models.radon_transformers import RadonTransformResult


class GalaxyRadonTransformResult:
    def __init__(self, source_id: str, bin_id: int, band_results: Dict[str, Optional[RadonTransformResult]], is_error: bool):
        self.source_id: str = source_id
        self.bin_id: int = bin_id
        self.band_results: Dict[str, Optional[RadonTransformResult]] = band_results
        self.is_error: bool = is_error

    @staticmethod
    def error(source_id: str, bin_id: int) -> 'GalaxyRadonTransformResult':
        return GalaxyRadonTransformResult(source_id, bin_id, {band: None for band in FITS_BANDS}, True)
