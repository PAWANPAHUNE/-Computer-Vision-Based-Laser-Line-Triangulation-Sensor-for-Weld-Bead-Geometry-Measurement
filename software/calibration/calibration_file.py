"""Calibration JSON: building, hashing and saving.

The file holds a camera section and a laser-plane section. An ``integrity_sha256`` over
the whole content detects manual edits; the laser section stores the hash of the camera
section it was measured with, so a new camera calibration invalidates the old laser plane.
A file is never trusted just because it exists: see ``calibration/validation.py``.
"""
from __future__ import annotations

import hashlib
import json
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from calibration.camera_calibration import IntrinsicsResult
from calibration.checkerboard import CheckerboardSpec
from calibration.laser_plane_calibration import LaserPlaneResult
from version import CALIBRATION_SCHEMA_VERSION, SOFTWARE_NAME, SOFTWARE_VERSION


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def canonical_hash(obj: Any) -> str:
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def software_info() -> dict[str, str]:
    return {"name": SOFTWARE_NAME, "version": SOFTWARE_VERSION, "opencv": cv2.__version__,
            "numpy": np.__version__, "python": platform.python_version()}


def camera_section(result: IntrinsicsResult) -> dict[str, Any]:
    if not result.ok:
        raise ValueError("Camera calibration did not pass validation; it cannot be saved.")
    return {
        "status": "valid",
        "calibrated_utc": _now(),
        "image_width": int(result.image_size[0]),
        "image_height": int(result.image_size[1]),
        "camera_matrix": np.asarray(result.camera_matrix, float).tolist(),
        "dist_coeffs": np.asarray(result.dist_coeffs, float).reshape(-1).tolist(),
        "distortion_model": "opencv_k1_k2_p1_p2_k3",
        "reprojection_error_px": float(result.rms_px),
        "per_view_errors_px": [float(e) for e in result.per_view_errors_px],
        "num_views": int(result.num_views),
        "view_names": list(result.view_names),
        "coverage_cells_of_9": int(result.coverage_cells),
        "tilt_range_deg": float(result.tilt_range_deg),
        "checkerboard": result.spec.to_dict(),
    }


def laser_section(result: LaserPlaneResult, spec: CheckerboardSpec, camera_sec: dict[str, Any]) -> dict[str, Any]:
    if not result.ok:
        raise ValueError("Laser-plane calibration did not pass validation; it cannot be saved.")
    return {
        "status": "valid",
        "calibrated_utc": _now(),
        "method": "checkerboard_pnp_ray_plane_intersection",
        "coefficients": [float(v) for v in result.plane],
        "equation": "a*X + b*Y + c*Z + d = 0 (camera frame, mm, |(a,b,c)| = 1, d <= 0)",
        "rms_residual_mm": float(result.rms_mm),
        "max_residual_mm": float(result.max_abs_mm),
        "num_poses": int(result.num_poses),
        "num_points": int(result.num_points),
        "inlier_fraction": float(result.inlier_fraction),
        "pose_spread_mm": float(result.pose_spread_mm),
        "depth_range_mm": [float(v) for v in result.depth_range_mm],
        "per_pose_rms_mm": {k: float(v) for k, v in result.per_pose_rms_mm.items()},
        "target": {"type": "printed_checkerboard_on_flat_rigid_board", **spec.to_dict()},
        "camera_section_sha256": canonical_hash(camera_sec),
    }


def new_calibration(cfg: dict[str, Any]) -> dict[str, Any]:
    fx = cfg["fixture"]
    return {
        "schema_version": CALIBRATION_SCHEMA_VERSION,
        "software": software_info(),
        "created_utc": _now(),
        "camera": None,
        "laser_plane": None,
        "hardware": {"fixture_id": fx["fixture_id"], "camera_tilt_setting_deg": fx["camera_tilt_setting_deg"],
                     "notes": fx.get("notes", ""), "camera_model": "Arducam UC-852 Rev.A (USB)"},
    }


def with_integrity(data: dict[str, Any]) -> dict[str, Any]:
    body = {k: v for k, v in data.items() if k != "integrity_sha256"}
    body["updated_utc"] = _now()
    body["software"] = software_info()
    body["integrity_sha256"] = canonical_hash({k: v for k, v in body.items() if k != "integrity_sha256"})
    return body


def integrity_ok(data: dict[str, Any]) -> bool:
    stored = data.get("integrity_sha256")
    if not isinstance(stored, str):
        return False
    try:
        return canonical_hash({k: v for k, v in data.items() if k != "integrity_sha256"}) == stored
    except (TypeError, ValueError):
        return False


def save_calibration(data: dict[str, Any], path: Path) -> Path:
    """Write atomically; the previous file is kept as ``<name>.<timestamp>.bak``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    final = with_integrity(data)
    if path.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(path, path.with_name(f"{path.stem}.{stamp}.bak"))
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(final, indent=2, allow_nan=False), encoding="utf-8")
    tmp.replace(path)
    return path


def load_calibration_json(path: Path) -> dict[str, Any]:
    """Raise FileNotFoundError / ValueError with a readable message."""
    if not path.exists():
        raise FileNotFoundError(f"Calibration file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Calibration file is not valid JSON (line {exc.lineno}): {exc.msg}") from exc
    if not isinstance(data, dict):
        raise ValueError("Calibration file must contain a JSON object.")
    return data
