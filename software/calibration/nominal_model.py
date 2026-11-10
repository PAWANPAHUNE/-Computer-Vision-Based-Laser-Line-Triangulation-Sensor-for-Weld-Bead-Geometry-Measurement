"""Nominal (uncalibrated) camera + laser geometry built from physical parameters.

This is an APPROXIMATE model, used for two things only:
1. clearly-labelled EXPERIMENTAL mm estimates in uncalibrated mode (only when
   ``calibration.allow_uncalibrated_metric_estimates: true`` and every parameter is known);
2. generating synthetic test scenes with known ground truth.

Rig frame (mm), fixed to the sensor fixture:
* origin = camera optical centre;
* +X = from the camera toward the laser (the baseline direction);
* +Z = the direction the fixture looks (normal to the fixture plate);
* +Y = Z x X (along the projected laser line when the fan is perpendicular to the baseline).

Laser plane: contains the laser emitter at (baseline, 0, 0) and the fan direction +Y.
``laser_plane_angle_deg`` tilts the beam toward the camera (0 = beam along +Z):
``cos(a)*X + sin(a)*Z - baseline*cos(a) = 0``.

Camera orientation: ``camera_pitch_deg`` turns the optical axis from +Z toward +X (the laser),
about the rig Y axis (the yoke pivot of fixture v3). ``camera_yaw_deg`` turns it about the rig
X axis. ``camera_roll_deg`` rotates the image about the optical axis. Camera axes in rig
coordinates are the columns of ``Rx(yaw) @ Ry(pitch) @ Rz(roll)``.

Assumptions (all must hold for the estimate to mean anything): ideal pinhole, zero lens
distortion, principal point at the image centre, square pixels, exact angles and baseline,
laser fan exactly perpendicular to the baseline.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from calibration.triangulation import normalize_plane

REQUIRED_FOR_NOMINAL = (
    "camera.focal_length_mm",
    "geometry.camera_to_laser_baseline_mm",
    "geometry.camera_pitch_deg",
    "geometry.camera_yaw_deg",
    "geometry.camera_roll_deg",
    "geometry.laser_plane_angle_deg",
)

ASSUMPTIONS = [
    "Ideal pinhole camera with zero lens distortion (not verified).",
    "Principal point exactly at the image centre and square pixels.",
    "Focal length, pixel pitch, baseline and all angles exactly as typed in the configuration.",
    "Laser fan exactly perpendicular to the camera-laser baseline.",
    "Height is measured inside the laser plane; equals true reinforcement height only when the laser "
    "plane is perpendicular to the base metal.",
]


def _rx(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]], dtype=np.float64)


def _ry(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], dtype=np.float64)


def _rz(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=np.float64)


def camera_axes_in_rig(pitch_deg: float, yaw_deg: float = 0.0, roll_deg: float = 0.0) -> np.ndarray:
    return _rx(math.radians(yaw_deg)) @ _ry(math.radians(pitch_deg)) @ _rz(math.radians(roll_deg))


def rig_to_camera_rotation(pitch_deg: float, yaw_deg: float = 0.0, roll_deg: float = 0.0) -> np.ndarray:
    """R such that P_camera = R @ P_rig (both frames share the origin)."""
    return camera_axes_in_rig(pitch_deg, yaw_deg, roll_deg).T


def laser_plane_rig(baseline_mm: float, laser_angle_deg: float) -> np.ndarray:
    a = math.radians(laser_angle_deg)
    return np.array([math.cos(a), 0.0, math.sin(a), -baseline_mm * math.cos(a)])


def plane_rig_to_camera(plane_rig: np.ndarray, R_rig_to_cam: np.ndarray) -> np.ndarray:
    n_cam = R_rig_to_cam @ np.asarray(plane_rig[:3], np.float64)
    return normalize_plane(np.append(n_cam, plane_rig[3]))


def intrinsics_from_specs(focal_length_mm: float, pixel_pitch_um: float, width: int, height: int) -> np.ndarray:
    f_px = focal_length_mm / (pixel_pitch_um / 1000.0)
    return np.array([[f_px, 0.0, (width - 1) / 2.0], [0.0, f_px, (height - 1) / 2.0], [0.0, 0.0, 1.0]])


@dataclass
class NominalModel:
    camera_matrix: np.ndarray
    dist_coeffs: np.ndarray
    laser_plane_camera: np.ndarray
    R_rig_to_cam: np.ndarray
    image_size: tuple[int, int]
    assumptions: list[str] = field(default_factory=lambda: list(ASSUMPTIONS))


def missing_nominal_parameters(cfg: dict[str, Any]) -> list[str]:
    missing = []
    for key in REQUIRED_FOR_NOMINAL:
        section, name = key.split(".")
        if cfg.get(section, {}).get(name) is None:
            missing.append(key)
    cam = cfg.get("camera", {})
    if cam.get("pixel_pitch_um") is None and cam.get("sensor_width_mm") is None:
        missing.append("camera.pixel_pitch_um (or camera.sensor_width_mm)")
    return missing


def build_nominal_model(cfg: dict[str, Any], image_size: tuple[int, int]) -> NominalModel:
    """Build the nominal model for an image of ``image_size = (width, height)``. Raises ValueError if incomplete."""
    missing = missing_nominal_parameters(cfg)
    if missing:
        raise ValueError("Nominal geometry needs these values in config.yaml: " + ", ".join(missing))
    cam, geo = cfg["camera"], cfg["geometry"]
    width, height = image_size
    pitch_um = cam["pixel_pitch_um"] if cam.get("pixel_pitch_um") is not None else \
        cam["sensor_width_mm"] * 1000.0 / width
    K = intrinsics_from_specs(cam["focal_length_mm"], pitch_um, width, height)
    R = rig_to_camera_rotation(geo["camera_pitch_deg"], geo["camera_yaw_deg"], geo["camera_roll_deg"])
    plane = plane_rig_to_camera(laser_plane_rig(geo["camera_to_laser_baseline_mm"], geo["laser_plane_angle_deg"]), R)
    return NominalModel(camera_matrix=K, dist_coeffs=np.zeros(5), laser_plane_camera=plane, R_rig_to_cam=R,
                        image_size=(width, height))
