"""Synthetic scenes with KNOWN ground truth (for tests and the demo).

Nothing here describes the real hardware. Synthetic accuracy says the algorithms are
consistent; it says nothing about the accuracy of the physical system.

* ``SyntheticRig``: camera intrinsics, optional distortion, and a laser plane built with the
  nominal rig geometry (see calibration/nominal_model.py).
* ``render_weld_image``: workpiece plane at ``working_distance_mm`` with an elliptical-cap bead
  running along the rig X axis; the laser line cuts across it.
* ``render_board_image``: printed checkerboard on a flat board at a known pose, optionally
  with the laser line on it (for camera and laser-plane calibration tests).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache

import cv2
import numpy as np

from calibration.checkerboard import CheckerboardSpec
from calibration.nominal_model import laser_plane_rig, plane_rig_to_camera, rig_to_camera_rotation
from calibration.triangulation import point_plane_distances


PAPER_LEVEL = 170.0


@dataclass
class SyntheticRig:
    width: int = 1280
    height: int = 800
    focal_px: float = 1400.0
    baseline_mm: float = 55.0
    pitch_deg: float = 20.0
    yaw_deg: float = 0.0
    roll_deg: float = 0.0
    laser_angle_deg: float = 0.0
    dist_coeffs: np.ndarray = field(default_factory=lambda: np.zeros(5))

    @property
    def K(self) -> np.ndarray:
        return np.array([[self.focal_px, 0, (self.width - 1) / 2], [0, self.focal_px, (self.height - 1) / 2],
                         [0, 0, 1]], dtype=np.float64)

    @property
    def R(self) -> np.ndarray:
        return rig_to_camera_rotation(self.pitch_deg, self.yaw_deg, self.roll_deg)

    @property
    def laser_plane_camera(self) -> np.ndarray:
        return plane_rig_to_camera(laser_plane_rig(self.baseline_mm, self.laser_angle_deg), self.R)

    def config_geometry(self) -> dict:
        """Values for config.yaml that make the nominal model equal to this rig (pixel pitch 3 um)."""
        return {"camera": {"focal_length_mm": self.focal_px * 0.003, "pixel_pitch_um": 3.0},
                "geometry": {"camera_to_laser_baseline_mm": self.baseline_mm, "camera_pitch_deg": self.pitch_deg,
                             "camera_yaw_deg": self.yaw_deg, "camera_roll_deg": self.roll_deg,
                             "laser_plane_angle_deg": self.laser_angle_deg}}

    def project(self, points_cam: np.ndarray) -> np.ndarray:
        uv, _ = cv2.projectPoints(np.asarray(points_cam, np.float64).reshape(-1, 1, 3), np.zeros(3), np.zeros(3),
                                  self.K, self.dist_coeffs)
        return uv.reshape(-1, 2)


@dataclass
class BeadSpec:
    width_mm: float = 8.0
    height_mm: float = 2.0
    center_mm: float = 0.0             # bead centre along the laser line (rig Y)
    working_distance_mm: float = 150.0  # rig Z of the base metal
    base_slope: float = 0.0            # dZ/dY of the base metal (tilted plate)


def bead_height(y: np.ndarray, bead: BeadSpec) -> np.ndarray:
    """Elliptical cap: h = H * sqrt(1 - (2u/W)^2) inside the bead, 0 outside."""
    u = 2.0 * (np.asarray(y) - bead.center_mm) / bead.width_mm
    return np.where(np.abs(u) < 1, bead.height_mm * np.sqrt(np.clip(1 - u ** 2, 0, None)), 0.0)


def weld_curve_rig(y: np.ndarray, rig: SyntheticRig, bead: BeadSpec) -> np.ndarray:
    """3D points (rig frame) where the laser plane meets the bead surface."""
    z = bead.working_distance_mm + bead.base_slope * y - bead_height(y, bead)
    x = rig.baseline_mm - z * math.tan(math.radians(rig.laser_angle_deg))
    return np.column_stack([x, y, z])


def _background(rng, h, w, level=85.0) -> np.ndarray:
    base = rng.normal(0, 1, (h // 8 + 1, w // 8 + 1)).astype(np.float32)
    base = cv2.resize(cv2.GaussianBlur(base, (0, 0), 3), (w, h)) * 12 + level
    streaks = cv2.GaussianBlur(rng.normal(0, 1, (h, w)).astype(np.float32), (0, 0), sigmaX=15, sigmaY=0.8) * 20
    gray = np.clip(base + streaks, 0, 255)
    return np.dstack([gray * 0.97, gray, gray * 1.02])


def _compose(bg: np.ndarray, stripe: np.ndarray, intensity: float, noise: float, rng) -> np.ndarray:
    img = bg.copy()
    img[..., 2] += intensity * stripe
    img[..., 1] += 0.12 * intensity * stripe
    img[..., 0] += 0.08 * intensity * stripe
    img += rng.normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def render_weld_image(rig: SyntheticRig, bead: BeadSpec, intensity: float = 170.0, noise: float = 3.0,
                      stripe_sigma_px: float = 1.6, gaps_mm: list[tuple[float, float]] | None = None,
                      reflection: bool = False, seed: int = 0) -> tuple[np.ndarray, dict]:
    rng = np.random.default_rng(seed)
    h, w = rig.height, rig.width
    ys = np.arange(-200.0, 200.0, 0.01)
    curve = weld_curve_rig(ys, rig, bead)
    cam = curve @ rig.R.T
    front = cam[:, 2] > 1
    uv = rig.project(cam[front])
    keep = (uv[:, 0] > -5) & (uv[:, 0] < w + 5) & (uv[:, 1] > -5) & (uv[:, 1] < h + 5)
    ys_kept = ys[front][keep]
    uv = uv[keep]
    if gaps_mm:
        for a, b in gaps_mm:
            g = (ys_kept >= a) & (ys_kept <= b)
            uv[g] = np.nan
    stripe = splat_curve(uv, (h, w), stripe_sigma_px)
    if reflection:
        refl = np.zeros_like(stripe)
        cv2.ellipse(refl, (int(w * 0.15), int(h * 0.25)), (25, 6), 30, 0, 360, 1.0, -1)
        stripe = np.maximum(stripe, cv2.GaussianBlur(refl, (0, 0), 3) * 0.8)
    img = _compose(_background(rng, h, w), stripe, intensity, noise, rng)

    # Ground truth in pixels: projected bead edges and peak relative to the projected base line.
    edges = np.array([bead.center_mm - bead.width_mm / 2, bead.center_mm + bead.width_mm / 2])
    base_pts = weld_curve_rig(edges, rig, BeadSpec(**{**bead.__dict__, "height_mm": 0.0})) @ rig.R.T
    peak_pt = weld_curve_rig(np.array([bead.center_mm]), rig, bead) @ rig.R.T
    e_uv = rig.project(base_pts)
    p_uv = rig.project(peak_pt)[0]
    d = e_uv[1] - e_uv[0]
    nrm = np.array([-d[1], d[0]]) / np.linalg.norm(d)
    truth = {"width_mm": bead.width_mm, "height_mm": bead.height_mm,
             "width_px": float(np.linalg.norm(d)), "height_px": float(abs((p_uv - e_uv[0]) @ nrm)),
             "edge_uv": e_uv, "peak_uv": p_uv}
    return img, truth


def splat_curve(uv: np.ndarray, shape: tuple[int, int], sigma_px: float) -> np.ndarray:
    """Render a curve as a Gaussian ridge (peak ~1) with exact sub-pixel positions.

    Each dense sample adds a Gaussian weighted by its arc length, so the result does not depend on
    the sampling density. NaN samples create gaps.
    """
    h, w = shape
    out = np.zeros(h * w, np.float64)
    ok = np.all(np.isfinite(uv), axis=1)
    seg_len = np.zeros(len(uv))
    if len(uv) > 1:
        d = np.linalg.norm(np.diff(uv, axis=0), axis=1)
        d = np.where(np.isfinite(d), d, 0.0)
        seg_len[:-1] += 0.5 * d
        seg_len[1:] += 0.5 * d
    pts, wts = uv[ok], seg_len[ok]
    r = int(math.ceil(3.5 * sigma_px))
    base_u = np.floor(pts[:, 0]).astype(int)
    base_v = np.floor(pts[:, 1]).astype(int)
    for dv in range(-r, r + 2):
        for du in range(-r, r + 2):
            uu, vv = base_u + du, base_v + dv
            inside = (uu >= 0) & (uu < w) & (vv >= 0) & (vv < h)
            d2 = (uu - pts[:, 0]) ** 2 + (vv - pts[:, 1]) ** 2
            val = wts * np.exp(-0.5 * d2 / sigma_px ** 2)
            np.add.at(out, (vv[inside] * w + uu[inside]), val[inside])
    return (out.reshape(h, w) / (math.sqrt(2 * math.pi) * sigma_px)).astype(np.float32)


@lru_cache(maxsize=4)
def _pixel_rays(width: int, height: int, K_bytes: bytes, dist_bytes: bytes, ss: int) -> np.ndarray:
    K = np.frombuffer(K_bytes).reshape(3, 3)
    dist = np.frombuffer(dist_bytes)
    offs = (np.arange(ss) + 0.5) / ss - 0.5
    us, vs = [], []
    for oy in offs:
        for ox in offs:
            uu, vv = np.meshgrid(np.arange(width) + ox, np.arange(height) + oy)
            us.append(uu)
            vs.append(vv)
    uv = np.stack([np.concatenate([u.ravel() for u in us]), np.concatenate([v.ravel() for v in vs])], 1)
    xy = cv2.undistortPoints(uv.reshape(-1, 1, 2).astype(np.float64), K, dist).reshape(-1, 2)
    return np.column_stack([xy, np.ones(len(xy))])


def render_board_image(rig: SyntheticRig, spec: CheckerboardSpec, rvec, tvec, laser_on: bool = False,
                       laser_sigma_mm: float = 0.35, intensity: float = 80.0, noise: float = 2.0, ss: int = 2,
                       paper_margin_mm: float = 20.0, seed: int = 0) -> np.ndarray:
    """Checkerboard (inner corner (0,0) at board origin) on white paper, seen by the rig camera."""
    rng = np.random.default_rng(seed)
    w, h = rig.width, rig.height
    rays = _pixel_rays(w, h, rig.K.tobytes(), np.asarray(rig.dist_coeffs, np.float64).tobytes(), ss)
    R, _ = cv2.Rodrigues(np.asarray(rvec, np.float64).reshape(3, 1))
    t = np.asarray(tvec, np.float64).reshape(3)
    n = R[:, 2]
    with np.errstate(divide="ignore", invalid="ignore"):
        s = (n @ t) / (rays @ n)
    P = rays * s[:, None]
    Pb = (P - t) @ R
    xb, yb = Pb[:, 0], Pb[:, 1]
    sq = spec.square_size_mm
    cols, rows = spec.squares
    in_sq = (xb >= -sq) & (xb < (cols - 1) * sq) & (yb >= -sq) & (yb < (rows - 1) * sq)
    in_paper = (xb >= -sq - paper_margin_mm) & (xb < (cols - 1) * sq + paper_margin_mm) & \
               (yb >= -sq - paper_margin_mm) & (yb < (rows - 1) * sq + paper_margin_mm) & (s > 0)
    checker = ((np.floor(xb / sq) + np.floor(yb / sq)) % 2 == 0)
    gray = np.where(in_paper, PAPER_LEVEL, 60.0)   # exposure set so the laser on white paper does not clip
    gray = np.where(in_sq & checker, 20.0, gray)
    red = np.zeros_like(gray)
    if laser_on:
        dist_mm = np.abs(point_plane_distances(np.nan_to_num(P), rig.laser_plane_camera))
        reflect = gray / PAPER_LEVEL  # laser light is dimmed by the same surface reflectance as room light
        red = np.exp(-0.5 * (dist_mm / laser_sigma_mm) ** 2) * reflect * (s > 0)
    k = ss * ss
    gray = gray.reshape(k, h, w).mean(axis=0)
    red = red.reshape(k, h, w).mean(axis=0)
    img = np.dstack([gray, gray, gray]).astype(np.float64)
    img[..., 2] += intensity * red
    img[..., 1] += 0.1 * intensity * red * 0.2
    img[..., 0] += 0.05 * intensity * red * 0.2
    img += rng.normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8)


def look_at_pose(distance_mm: float, tilt_x_deg: float, tilt_y_deg: float, spec: CheckerboardSpec,
                 shift_xy_mm: tuple[float, float] = (0.0, 0.0)) -> tuple[np.ndarray, np.ndarray]:
    """Board pose (rvec, tvec) with the board centre on the optical axis at ``distance_mm``, tilted."""
    R = cv2.Rodrigues(np.array([math.radians(tilt_x_deg), 0, 0]))[0] @ \
        cv2.Rodrigues(np.array([0, math.radians(tilt_y_deg), 0]))[0]
    centre_b = np.array([(spec.inner_corners_cols - 1) * spec.square_size_mm / 2,
                         (spec.inner_corners_rows - 1) * spec.square_size_mm / 2, 0.0])
    t = np.array([shift_xy_mm[0], shift_xy_mm[1], distance_mm]) - R @ centre_b
    return cv2.Rodrigues(R)[0].reshape(3), t
