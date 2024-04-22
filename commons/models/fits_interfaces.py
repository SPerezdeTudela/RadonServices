import os
from typing import Dict, Optional

import numpy as np
from astropy.io import fits

from commons.constants.fits_constants import FITS_BANDS, FITS_DIRECTORY_PATH
from commons.models.denoisers import AbstractDenoiser
from commons.models.mask_generators import AbstractMaskGenerator


class BandFitsBuilder:
    def __init__(self, fits_data: np.ndarray):
        self._fits_data: np.ndarray = fits_data

        self._should_preprocess: bool = True
        self._mask_generator: Optional[AbstractMaskGenerator] = None
        self._denoiser: Optional[AbstractDenoiser] = None

    def mask(self, mask_generator: AbstractMaskGenerator) -> "BandFitsBuilder":
        self._mask_generator = mask_generator
        return self

    def denoise(self, denoiser: AbstractDenoiser) -> "BandFitsBuilder":
        self._denoiser = denoiser
        return self

    def build(self) -> np.ndarray:
        if self._should_preprocess:
            self._fits_data = self._preprocess(self._fits_data)

        if self._mask_generator:
            mask = self._mask_generator.generate((self._fits_data.shape[0], self._fits_data.shape[1]))
            self._fits_data = self._mask_generator.apply_mask(self._fits_data)

        if self._denoiser:
            # TODO: fix this
            self._fits_data = self._denoiser.denoise(self._fits_data, mask)

        return self._fits_data

    @staticmethod
    def _preprocess(fits_data) -> np.ndarray:
        # Shift FITS data to be non-negative
        shift: float = np.min(fits_data)
        if shift < 0:
            fits_data += abs(shift)

        # TODO: Add more preprocessing steps
        return fits_data


class GalaxyFitsData:
    """ Data holder for a single galaxy's FITS file """

    def __init__(self, source_id: str, bin_id: str, fits_data_list: np.ndarray):
        self.source_id: str = source_id
        self.bin_id: str = bin_id

        self._band_data_map: Dict[str, Optional[BandFitsBuilder]] = {}
        for i, band in enumerate(FITS_BANDS):
            fits_data = fits_data_list[i]
            is_valid = self._validate_fits(fits_data)
            self._band_data_map[band] = BandFitsBuilder(fits_data) if is_valid else None

    @staticmethod
    def _validate_fits(fits_data: np.ndarray) -> bool:
        """ Determines whether the FITS data is a valid galaxy image """
        # Check if FITS data is empty or contains NaNs
        if not fits_data.any() or np.any(np.isnan(fits_data)):
            return False
        # TODO: Add more validation checks
        return True

    def get_band_data(self, band: str) -> Optional[BandFitsBuilder]:
        if band not in FITS_BANDS:
            raise ValueError(f"Invalid band: {band}, must be one of {FITS_BANDS}")
        return self._band_data_map[band]


class AbstractFitsInterface:
    """ Interface for building FITS data """

    def load_fits(self, source_id: str, bin_id: str) -> GalaxyFitsData:
        """ Loads FITS data for a single galaxy, might raise exceptions """
        raise NotImplementedError

    def save_fits(self, source_id: str, bin_id: str, raw_bytes: bytes):
        """ Saves FITS data for a single galaxy, might raise exceptions """
        raise NotImplementedError

    def _build_fits_path(self, source_id: str, bin_id: str) -> str:
        return f"{FITS_DIRECTORY_PATH}/b{bin_id}/{source_id}.fits"


class LinuxFitsInterface(AbstractFitsInterface):
    def load_fits(self, source_id: str, bin_id: str) -> GalaxyFitsData:
        fits_path = self._build_fits_path(source_id, bin_id)
        with fits.open(fits_path) as hdu_list:
            fits_data_list: np.ndarray = hdu_list[0].data
            hdu_list.close()

        return GalaxyFitsData(source_id, bin_id, fits_data_list)

    def save_fits(self, source_id: str, bin_id: str, raw_bytes: bytes):
        fits_path = self._build_fits_path(source_id, bin_id)
        os.makedirs(os.path.dirname(fits_path), exist_ok=True)

        with open(fits_path, "wb") as file:
            file.write(raw_bytes)


class LocalTestingFitsInterface(LinuxFitsInterface):
    """ Fits interface for testing on local machine, changes the FITS directory path """

    def _build_fits_path(self, source_id: str, bin_id: str) -> str:
        local_fits_directory_path: str = "C:/One/UCI/Alberto/data/fits"
        return f"{local_fits_directory_path}/b{bin_id}/{source_id}.fits"


if __name__ == "__main__":
    import matplotlib.pyplot as plt
    from commons.models.mask_generators import CircleMaskGenerator

    fits_interface: AbstractFitsInterface = LocalTestingFitsInterface()
    galaxy_fits_data: GalaxyFitsData = fits_interface.load_fits("2305889330436758656", "6")

    target_band: str = "g"
    band_data: BandFitsBuilder = galaxy_fits_data.get_band_data(target_band)

    mask_generator: AbstractMaskGenerator = CircleMaskGenerator()
    plt.imshow(band_data.mask(mask_generator).build(), cmap="gray")
    plt.show()
