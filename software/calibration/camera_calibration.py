"""Camera intrinsic calibration from checkerboard views (OpenCV pinhole + 5-term distortion).

Camera intrinsics alone are NOT enough for 3D laser triangulation: the laser plane must be
calibrated separately (see ``laser_plane_calibration.py``).

View policy (all values from ``calibration.camera_intrinsics`` in config.yaml):
* at least ``min_views`` accepted views (the UI asks for ``recommended_views``);
* the board must have touched at least ``min_coverage_cells`` cells of a 3 x 3 image grid;
* board tilt angles must span at least ``min_tilt_range_deg``;
* RMS reprojection error at most ``max_reprojection_error_px``.
If any check fails the result is rejected and the UI asks for more / better views.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from calibration.checkerboard import CheckerboardSpec, find_checkerboard, sharpness

MIN_SHARPNESS = 30.0


@dataclass
class CalibrationView:
    name: str
    image_size: tuple[int, int]
    ok: bool
    reason: str = ""
    corners: np.ndarray | None = None
    sharpness: float = 0.0
    board_area_fraction: float = 0.0
    cells: frozenset = frozenset()


def grid_cells(points_uv: np.ndarray, image_size: tuple[int, int], n: int = 3) -> frozenset:
    w, h = image_size
    cols = np.clip((points_uv[:, 0] / w * n).astype(int), 0, n - 1)
    rows = np.clip((points_uv[:, 1] / h * n).astype(int), 0, n - 1)
    return frozenset(zip(rows.tolist(), cols.tolist()))


def detect_view(image_bgr: np.ndarray, spec: CheckerboardSpec, name: str) -> CalibrationView:
    if image_bgr is None or image_bgr.size == 0:
        return CalibrationView(name, (0, 0), False, "The image could not be read.")
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY) if image_bgr.ndim == 3 else image_bgr
    size = (gray.shape[1], gray.shape[0])
    sharp = sharpness(gray)
    found, corners = find_checkerboard(gray, spec)
    if not found:
        return CalibrationView(name, size, False,
                               f"Checkerboard with {spec.inner_corners_cols} x {spec.inner_corners_rows} inner corners "
                               "not found. Show the whole board, avoid glare, check focus and the corner numbers.",
                               sharpness=sharp)
    uv = corners.reshape(-1, 2)
    hull = cv2.convexHull(uv.astype(np.float32))
    area = float(cv2.contourArea(hull)) / (size[0] * size[1])
    view = CalibrationView(name, size, True, "", corners, sharp, area, grid_cells(uv, size))
    if sharp < MIN_SHARPNESS:
        view.reason = f"Accepted, but the image looks blurry (sharpness {sharp:.0f}). Hold the board still."
    return view


@dataclass
class IntrinsicsResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    camera_matrix: np.ndarray | None = None
    dist_coeffs: np.ndarray | None = None
    rms_px: float | None = None
    per_view_errors_px: list[float] = field(default_factory=list)
    view_names: list[str] = field(default_factory=list)
    tilt_angles_deg: list[float] = field(default_factory=list)
    coverage_cells: int = 0
    image_size: tuple[int, int] | None = None
    spec: CheckerboardSpec | None = None
    num_views: int = 0
    needs_more_views: bool = False

    @property
    def tilt_range_deg(self) -> float:
        return float(max(self.tilt_angles_deg) - min(self.tilt_angles_deg)) if self.tilt_angles_deg else 0.0


def calibrate_intrinsics(views: list[CalibrationView], spec: CheckerboardSpec, policy: dict[str, Any]) -> IntrinsicsResult:
    good = [v for v in views if v.ok and v.corners is not None]
    res = IntrinsicsResult(ok=False, spec=spec)
    if not good:
        res.errors.append("No accepted checkerboard views yet.")
        res.needs_more_views = True
        return res
    size = good[0].image_size
    same = [v for v in good if v.image_size == size]
    if len(same) != len(good):
        res.warnings.append(f"{len(good) - len(same)} view(s) have a different resolution than {size[0]}x{size[1]} "
                            "and were not used. Calibrate at the resolution you will measure with.")
    good = same
    res.image_size = size
    res.num_views = len(good)
    if len(good) < policy["min_views"]:
        res.errors.append(f"Only {len(good)} accepted view(s). Collect at least {policy['min_views']} "
                          f"(recommended {policy['recommended_views']}).")
        res.needs_more_views = True
        return res

    objp = spec.object_points()
    obj = [objp.copy() for _ in good]
    img = [v.corners.astype(np.float32) for v in good]
    # fix_k3: keep the 3rd radial term at 0. Recommended when the board never reached the image corners:
    # a free k3 then fits the data equally well but extrapolates wildly in the corners.
    flags = cv2.CALIB_FIX_K3 if policy.get("fix_k3", False) else 0
    rms, K, dist, rvecs, tvecs = cv2.calibrateCamera(obj, img, size, None, None, flags=flags)
    per_view = []
    tilts = []
    for o, i, rv, tv in zip(obj, img, rvecs, tvecs):
        proj, _ = cv2.projectPoints(o, rv, tv, K, dist)
        per_view.append(float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - i.reshape(-1, 2)) ** 2, axis=1)))))
        R, _ = cv2.Rodrigues(rv)
        tilts.append(math.degrees(math.acos(min(1.0, abs(float(R[2, 2]))))))
    cells = set()
    for v in good:
        cells |= set(v.cells)

    res.camera_matrix, res.dist_coeffs = K, dist.reshape(-1)
    res.rms_px = float(rms)
    res.per_view_errors_px = per_view
    res.view_names = [v.name for v in good]
    res.tilt_angles_deg = tilts
    res.coverage_cells = len(cells)

    w, h = size
    fx, fy, cx, cy = K[0, 0], K[1, 1], K[0, 2], K[1, 2]
    if not np.all(np.isfinite(K)) or not np.all(np.isfinite(dist)) or fx <= 0 or fy <= 0:
        res.errors.append("Calibration produced invalid numbers. Retake the views.")
    if not (0 < cx < w and 0 < cy < h):
        res.errors.append("The estimated image centre is outside the image. Retake more varied views.")
    if fx > 0 and fy > 0 and abs(fx / fy - 1.0) > 0.1:
        res.warnings.append(f"fx/fy = {fx / fy:.3f} is far from 1; check the views.")
    if res.rms_px > policy["max_reprojection_error_px"]:
        res.errors.append(f"Reprojection error {res.rms_px:.3f} px is above the limit "
                          f"{policy['max_reprojection_error_px']} px. Remove blurry views and add sharper ones.")
        res.needs_more_views = True
    if res.coverage_cells < policy["min_coverage_cells"]:
        empty = sorted({(r, c) for r in range(3) for c in range(3)} - cells)
        names = {0: "top", 1: "middle", 2: "bottom"}, {0: "left", 1: "centre", 2: "right"}
        where = ", ".join(f"{names[0][r]}-{names[1][c]}" for r, c in empty)
        res.errors.append(f"The board covered only {res.coverage_cells} of 9 image areas (need "
                          f"{policy['min_coverage_cells']}). Add views with the board in: {where}.")
        res.needs_more_views = True
    if res.tilt_range_deg < policy["min_tilt_range_deg"]:
        res.errors.append(f"Board tilt only varied by {res.tilt_range_deg:.1f} deg (need "
                          f"{policy['min_tilt_range_deg']}). Add views with the board tilted left/right and up/down.")
        res.needs_more_views = True
    if len(good) < policy["recommended_views"]:
        res.warnings.append(f"{len(good)} views used; {policy['recommended_views']} are recommended.")
    med = float(np.median(per_view))
    bad = [n for n, e in zip(res.view_names, per_view) if e > max(2.0 * med, 0.5)]
    if bad:
        res.warnings.append("These views fit much worse than the others (consider removing them): " + ", ".join(bad))
    res.ok = not res.errors
    return res
