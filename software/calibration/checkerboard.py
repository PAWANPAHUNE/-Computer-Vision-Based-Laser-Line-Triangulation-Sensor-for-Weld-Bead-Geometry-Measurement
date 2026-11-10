"""Checkerboard description and corner detection.

Corner detection is ported from the existing starter kit
(AI_Welding/arducam_laser_calibration_starter: ``find_board``): the sector-based
detector first, then the classic detector with sub-pixel refinement. The pattern size
is no longer hard-coded; it always comes from ``calibration.checkerboard`` in config.yaml.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class CheckerboardSpec:
    inner_corners_cols: int   # inner corners across = squares across - 1
    inner_corners_rows: int   # inner corners down   = squares down - 1
    square_size_mm: float

    @classmethod
    def from_config(cls, cfg: dict[str, Any]) -> "CheckerboardSpec":
        cb = cfg["calibration"]["checkerboard"]
        return cls(int(cb["inner_corners_cols"]), int(cb["inner_corners_rows"]), float(cb["square_size_mm"]))

    @property
    def pattern(self) -> tuple[int, int]:
        return (self.inner_corners_cols, self.inner_corners_rows)

    @property
    def squares(self) -> tuple[int, int]:
        return (self.inner_corners_cols + 1, self.inner_corners_rows + 1)

    def object_points(self) -> np.ndarray:
        """(N, 3) float32 board coordinates in mm, OpenCV corner order (row-major)."""
        objp = np.zeros((self.inner_corners_cols * self.inner_corners_rows, 3), np.float32)
        grid = np.mgrid[0:self.inner_corners_cols, 0:self.inner_corners_rows].T.reshape(-1, 2)
        objp[:, :2] = grid * self.square_size_mm
        return objp

    def outer_outline_mm(self, margin_mm: float = 0.0) -> np.ndarray:
        """Board-frame rectangle (4, 3) around ALL printed squares, enlarged by margin_mm."""
        s = self.square_size_mm
        x0, y0 = -s - margin_mm, -s - margin_mm
        x1 = self.inner_corners_cols * s + margin_mm
        y1 = self.inner_corners_rows * s + margin_mm
        return np.array([[x0, y0, 0], [x1, y0, 0], [x1, y1, 0], [x0, y1, 0]], dtype=np.float64)

    def to_dict(self) -> dict[str, Any]:
        return {"inner_corners_cols": self.inner_corners_cols, "inner_corners_rows": self.inner_corners_rows,
                "square_size_mm": self.square_size_mm}


def find_checkerboard(gray: np.ndarray, spec: CheckerboardSpec) -> tuple[bool, np.ndarray | None]:
    """Detect inner corners. Returns (found, corners (N, 1, 2) float32)."""
    pattern = spec.pattern
    if hasattr(cv2, "findChessboardCornersSB"):
        found, corners = cv2.findChessboardCornersSB(gray, pattern, flags=cv2.CALIB_CB_NORMALIZE_IMAGE)
        if found:
            return True, corners.astype(np.float32).reshape(-1, 1, 2)
    found, corners = cv2.findChessboardCorners(
        gray, pattern, flags=cv2.CALIB_CB_ADAPTIVE_THRESH | cv2.CALIB_CB_NORMALIZE_IMAGE)
    if found:
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                   (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
        return True, corners.astype(np.float32).reshape(-1, 1, 2)
    return False, None


def sharpness(gray: np.ndarray) -> float:
    """Variance of the Laplacian; low values mean blur."""
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def draw_corners(image_bgr: np.ndarray, spec: CheckerboardSpec, corners: np.ndarray | None, found: bool) -> np.ndarray:
    view = image_bgr.copy()
    if corners is not None:
        cv2.drawChessboardCorners(view, spec.pattern, corners, found)
    return view
