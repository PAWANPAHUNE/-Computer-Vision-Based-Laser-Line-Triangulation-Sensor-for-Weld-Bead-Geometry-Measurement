"""Turn stripe centres into profiles (pixel profile here; metric profile in calibration.triangulation)."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from vision.laser_detection import AXIS_COLUMNS, StripeResult


@dataclass
class PixelProfile:
    """Image-space profile.

    ``x``: position along the laser line (column index for a horizontal stripe,
    row index for a vertical stripe), px.
    ``y``: stripe centre across the line, px (NaN = missing). A weld bead moves the
    stripe across the line; this displacement is NOT a physical height.
    """
    axis: str
    x: np.ndarray
    y: np.ndarray
    confidence: np.ndarray

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.y)

    def image_uv(self) -> np.ndarray:
        """(N, 2) pixel coordinates (u = column, v = row) for every sample; NaN where missing."""
        if self.axis == AXIS_COLUMNS:
            return np.column_stack([self.x, self.y])
        return np.column_stack([self.y, self.x])


def pixel_profile(stripe: StripeResult) -> PixelProfile:
    return PixelProfile(axis=stripe.axis, x=stripe.positions.astype(np.float64),
                        y=stripe.centers.astype(np.float64), confidence=stripe.confidence.astype(np.float64))


def uv_to_profile_coords(axis: str, uv: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Inverse of :meth:`PixelProfile.image_uv`: returns (along, across)."""
    if axis == AXIS_COLUMNS:
        return uv[:, 0], uv[:, 1]
    return uv[:, 1], uv[:, 0]
