"""Laser triangulation mathematics (camera frame, millimetres).

Conventions
-----------
* Camera frame: OpenCV pinhole. X right, Y down, Z forward along the optical axis; origin
  at the optical centre. Units: mm.
* Plane: ``a*X + b*Y + c*Z + d = 0`` with ``(a, b, c)`` a unit normal and ``d <= 0``
  (the normal points away from the camera; ``|d|`` is the camera-to-plane distance).

Per stripe pixel: undistort -> normalised ray ``r = (x, y, 1)`` -> ``P = t*r`` with
``t = -d / (n . r)``. Rays almost parallel to the plane (angle below
``min_angle_deg``) and intersections behind the camera (``t <= 0``) are rejected.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np

REASON_OK = "ok"
REASON_PARALLEL = "ray_parallel_to_plane"
REASON_BEHIND = "behind_camera"
REASON_DEPTH = "outside_depth_range"
REASON_MISSING = "no_stripe"


class DegeneratePlaneError(ValueError):
    pass


def normalize_plane(coeffs) -> np.ndarray:
    """Scale ``(a, b, c, d)`` so that ``|(a, b, c)| = 1`` and ``d <= 0``. Rejects non-finite / zero normals."""
    p = np.asarray(coeffs, dtype=np.float64).reshape(-1)
    if p.size != 4 or not np.all(np.isfinite(p)):
        raise DegeneratePlaneError("A plane needs 4 finite coefficients (a, b, c, d).")
    norm = float(np.linalg.norm(p[:3]))
    if norm < 1e-12:
        raise DegeneratePlaneError("The plane normal (a, b, c) is zero.")
    p = p / norm
    if p[3] > 0:
        p = -p
    return p


def undistort_to_normalized(uv: np.ndarray, camera_matrix: np.ndarray, dist_coeffs: np.ndarray) -> np.ndarray:
    """Pixel (u, v) -> normalised, distortion-free image coordinates (x, y)."""
    uv = np.asarray(uv, dtype=np.float64).reshape(-1, 1, 2)
    if uv.shape[0] == 0:
        return np.zeros((0, 2))
    out = cv2.undistortPoints(uv, np.asarray(camera_matrix, np.float64), np.asarray(dist_coeffs, np.float64))
    return out.reshape(-1, 2)


def pixel_rays(uv: np.ndarray, camera_matrix: np.ndarray, dist_coeffs: np.ndarray) -> np.ndarray:
    xy = undistort_to_normalized(uv, camera_matrix, dist_coeffs)
    return np.column_stack([xy, np.ones(len(xy))])


def intersect_rays_with_plane(rays: np.ndarray, plane, min_angle_deg: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Intersect rays from the camera origin with a plane.

    Returns ``(points (N, 3) with NaN for rejected rays, reasons (N,) str)``.
    """
    p = normalize_plane(plane)
    n, d = p[:3], p[3]
    rays = np.asarray(rays, dtype=np.float64).reshape(-1, 3)
    norms = np.linalg.norm(rays, axis=1)
    denom = rays @ n
    with np.errstate(divide="ignore", invalid="ignore"):
        sin_angle = np.abs(denom) / norms
        t = -d / denom
    reasons = np.full(len(rays), REASON_OK, dtype=object)
    parallel = ~np.isfinite(sin_angle) | (sin_angle < math.sin(math.radians(min_angle_deg)))
    reasons[parallel] = REASON_PARALLEL
    behind = ~parallel & (~np.isfinite(t) | (t <= 0))
    reasons[behind] = REASON_BEHIND
    with np.errstate(invalid="ignore"):
        points = rays * t[:, None]
    points[reasons != REASON_OK] = np.nan
    return points, reasons


def triangulate_pixels(uv: np.ndarray, camera_matrix, dist_coeffs, plane, min_angle_deg: float = 2.0,
                       depth_range_mm: tuple[float, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Pixels (NaN allowed) -> 3D points on the laser plane, plus a reason per pixel."""
    uv = np.asarray(uv, dtype=np.float64).reshape(-1, 2)
    points = np.full((len(uv), 3), np.nan)
    reasons = np.full(len(uv), REASON_MISSING, dtype=object)
    ok = np.all(np.isfinite(uv), axis=1)
    if ok.any():
        rays = pixel_rays(uv[ok], camera_matrix, dist_coeffs)
        pts, why = intersect_rays_with_plane(rays, plane, min_angle_deg)
        if depth_range_mm is not None:
            lo, hi = depth_range_mm
            bad = (why == REASON_OK) & ((pts[:, 2] < lo) | (pts[:, 2] > hi))
            why[bad] = REASON_DEPTH
            pts[bad] = np.nan
        points[ok] = pts
        reasons[ok] = why
    return points, reasons


def board_plane_from_pose(rvec, tvec) -> np.ndarray:
    """Plane of a calibration board (board Z = 0) expressed in the camera frame."""
    R, _ = cv2.Rodrigues(np.asarray(rvec, np.float64).reshape(3, 1))
    n = R[:, 2]
    t = np.asarray(tvec, np.float64).reshape(3)
    return normalize_plane(np.append(n, -float(n @ t)))


def point_plane_distances(points: np.ndarray, plane) -> np.ndarray:
    p = normalize_plane(plane)
    return np.asarray(points, np.float64).reshape(-1, 3) @ p[:3] + p[3]


@dataclass
class PlaneFit:
    plane: np.ndarray
    residuals: np.ndarray       # signed distances of ALL points (mm)
    inliers: np.ndarray         # bool mask used in the final fit
    singular_values: np.ndarray

    @property
    def rms(self) -> float:
        r = self.residuals[self.inliers]
        return float(np.sqrt(np.mean(r ** 2))) if r.size else float("nan")

    @property
    def max_abs(self) -> float:
        r = self.residuals[self.inliers]
        return float(np.max(np.abs(r))) if r.size else float("nan")


def fit_plane(points: np.ndarray) -> PlaneFit:
    """Total-least-squares plane (SVD of centred points)."""
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    pts = pts[np.all(np.isfinite(pts), axis=1)]
    if len(pts) < 3:
        raise DegeneratePlaneError("At least 3 points are needed to fit a plane.")
    centroid = pts.mean(axis=0)
    _, s, vt = np.linalg.svd(pts - centroid, full_matrices=False)
    n = vt[2]
    plane = normalize_plane(np.append(n, -float(n @ centroid)))
    res = point_plane_distances(pts, plane)
    return PlaneFit(plane=plane, residuals=res, inliers=np.ones(len(pts), bool), singular_values=s)


def robust_fit_plane(points: np.ndarray, k_sigma: float = 3.0, iterations: int = 3) -> PlaneFit:
    """SVD plane fit with iterative rejection of points beyond ``k_sigma`` robust sigmas."""
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    pts = pts[np.all(np.isfinite(pts), axis=1)]
    fit = fit_plane(pts)
    inl = np.ones(len(pts), bool)
    for _ in range(iterations):
        res = point_plane_distances(pts, fit.plane)
        sigma = 1.4826 * np.median(np.abs(res[inl] - np.median(res[inl])))
        new = np.abs(res) <= max(k_sigma * sigma, 1e-9)
        if new.sum() < 3 or np.array_equal(new, inl):
            break
        inl = new
        fit = fit_plane(pts[inl])
    res = point_plane_distances(pts, fit.plane)
    return PlaneFit(plane=fit.plane, residuals=res, inliers=inl, singular_values=fit.singular_values)


def fit_line_3d(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Least-squares 3D line: (point, unit direction, RMS distance of points to the line)."""
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    pts = pts[np.all(np.isfinite(pts), axis=1)]
    c = pts.mean(axis=0)
    _, _, vt = np.linalg.svd(pts - c, full_matrices=False)
    direction = vt[0]
    diff = pts - c
    perp = diff - np.outer(diff @ direction, direction)
    return c, direction, float(np.sqrt(np.mean(np.sum(perp ** 2, axis=1))))


def robust_line_3d(points: np.ndarray, inlier_mm: float, iterations: int = 5):
    """3D line that ignores a few stray points (e.g. where the laser runs off the board edge).

    Returns (point, direction, rms of inliers, inlier mask). Starts from a median-scaled band so a
    handful of gross outliers cannot drag the first estimate, then refits on points within ``inlier_mm``.
    """
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    keep = np.ones(len(pts), bool)

    def residuals(mask):
        c = pts[mask].mean(axis=0)
        _, _, vt = np.linalg.svd(pts[mask] - c, full_matrices=False)
        d = pts - c
        return c, vt[0], np.linalg.norm(d - np.outer(d @ vt[0], vt[0]), axis=1)

    c, direction, r = residuals(keep)
    keep = r <= max(3.0 * float(np.median(r)), 0.5 * inlier_mm)
    for _ in range(iterations):
        if keep.sum() < 3:
            break
        c, direction, r = residuals(keep)
        new = r <= inlier_mm
        if np.array_equal(new, keep):
            break
        keep = new
    rms = float(np.sqrt(np.mean(r[keep] ** 2))) if keep.any() else float("inf")
    return c, direction, rms, keep


@dataclass
class PlaneProfile:
    s: np.ndarray        # mm along the laser line (across the bead)
    h: np.ndarray        # mm inside the laser plane, perpendicular to s, + toward the camera
    origin: np.ndarray
    e_s: np.ndarray
    e_h: np.ndarray


def points_to_plane_profile(points: np.ndarray, plane) -> PlaneProfile:
    """Express 3D laser points as 2D (s, h) coordinates inside the laser plane.

    ``e_s`` = principal direction of the points (the line direction), oriented so that
    ``s`` increases with the input order. ``e_h = n x e_s`` oriented toward the camera,
    so a bead that rises toward the camera has positive ``h``. NaN rows stay NaN.
    """
    p = normalize_plane(plane)
    n = p[:3]
    pts = np.asarray(points, np.float64).reshape(-1, 3)
    ok = np.all(np.isfinite(pts), axis=1)
    if ok.sum() < 2:
        raise DegeneratePlaneError("Need at least 2 valid 3D points to build a profile.")
    valid = pts[ok]
    origin = valid.mean(axis=0)
    centred = valid - origin
    centred_in_plane = centred - np.outer(centred @ n, n)
    _, _, vt = np.linalg.svd(centred_in_plane, full_matrices=False)
    e_s = vt[0] - (vt[0] @ n) * n
    e_s /= np.linalg.norm(e_s)
    if (valid[-1] - valid[0]) @ e_s < 0:
        e_s = -e_s
    e_h = np.cross(n, e_s)
    e_h /= np.linalg.norm(e_h)
    if e_h @ (-origin) < 0:
        e_h = -e_h
    s = np.full(len(pts), np.nan)
    h = np.full(len(pts), np.nan)
    s[ok] = (valid - origin) @ e_s
    h[ok] = (valid - origin) @ e_h
    return PlaneProfile(s=s, h=h, origin=origin, e_s=e_s, e_h=e_h)


def scale_intrinsics(camera_matrix: np.ndarray, from_size: tuple[int, int], to_size: tuple[int, int]) -> np.ndarray:
    """Rescale K for a uniformly scaled image (same field of view, no crop). Pixel-centre convention.

    Only valid if the camera bins/scales the full sensor; for a crop the result is wrong.
    """
    sx = to_size[0] / from_size[0]
    sy = to_size[1] / from_size[1]
    K = np.array(camera_matrix, dtype=np.float64).copy()
    K[0, 0] *= sx
    K[1, 1] *= sy
    K[0, 1] *= sx
    K[0, 2] = (K[0, 2] + 0.5) * sx - 0.5
    K[1, 2] = (K[1, 2] + 0.5) * sy - 0.5
    return K
