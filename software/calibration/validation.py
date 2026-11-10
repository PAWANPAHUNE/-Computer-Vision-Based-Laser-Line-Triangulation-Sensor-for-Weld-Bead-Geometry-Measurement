"""Calibration validity checks and operating-mode resolution.

Rules (from config.yaml, never overridden silently):
* ``calibration.enabled: false`` -> UNCALIBRATED mode. The calibration file is not read.
* ``calibration.enabled: true``  -> CALIBRATED mode. mm results require a calibration that
  passes EVERY check below. If it fails, the mode stays CALIBRATED but metric output is BLOCKED
  (and with ``require_valid_calibration: true`` all processing is blocked).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from calibration.calibration_file import canonical_hash, integrity_ok, load_calibration_json
from calibration.checkerboard import CheckerboardSpec
from calibration.triangulation import point_plane_distances, scale_intrinsics, triangulate_pixels
from utils.config_loader import resolve_project_path
from version import CALIBRATION_SCHEMA_VERSION

MODE_UNCALIBRATED = "uncalibrated"
MODE_CALIBRATED = "calibrated"
VALID_DIST_LENGTHS = (4, 5, 8, 12, 14)


@dataclass
class Check:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class CalibrationReport:
    path: Path | None = None
    data: dict[str, Any] | None = None
    checks: list[Check] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    camera_matrix: np.ndarray | None = None
    dist_coeffs: np.ndarray | None = None
    image_size: tuple[int, int] | None = None
    plane: np.ndarray | None = None
    camera_ok: bool = False
    laser_ok: bool = False

    def check(self, name: str, passed: bool, detail: str = "", error: str | None = None) -> bool:
        self.checks.append(Check(name, bool(passed), detail))
        if not passed:
            self.errors.append(error or f"{name}: {detail}")
        return bool(passed)

    @property
    def metric_ready(self) -> bool:
        return self.camera_ok and self.laser_ok and not self.errors

    @property
    def fingerprint(self) -> str | None:
        return self.data.get("integrity_sha256") if self.data else None


def _finite_matrix(value: Any, shape: tuple[int, ...]) -> np.ndarray | None:
    try:
        arr = np.asarray(value, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if arr.shape != shape or not np.all(np.isfinite(arr)):
        return None
    return arr


def validate_camera_section(cam: Any, cfg: dict[str, Any], report: CalibrationReport) -> None:
    if not report.check("Camera intrinsics present", isinstance(cam, dict), "present" if isinstance(cam, dict) else "missing",
                        "Camera intrinsics are missing. Run Calibration > 2. Camera Intrinsics."):
        return
    required = ("status", "image_width", "image_height", "camera_matrix", "dist_coeffs", "reprojection_error_px",
                "num_views", "checkerboard")
    missing = [k for k in required if k not in cam]
    if not report.check("Camera fields complete", not missing, ", ".join(missing),
                        f"Camera section is incomplete (missing {', '.join(missing)}). Recalibrate the camera."):
        return
    report.check("Camera status", cam["status"] == "valid", str(cam["status"]),
                 "Camera calibration is not marked valid. Recalibrate the camera.")
    K = _finite_matrix(cam["camera_matrix"], (3, 3))
    dist = None
    try:
        dist = np.asarray(cam["dist_coeffs"], dtype=np.float64).reshape(-1)
    except (TypeError, ValueError):
        pass
    w, h = cam.get("image_width"), cam.get("image_height")
    size_ok = isinstance(w, int) and isinstance(h, int) and w > 0 and h > 0
    report.check("Image size", size_ok, f"{w}x{h}", "Camera image size in the file is invalid.")
    k_ok = K is not None and K[0, 0] > 0 and K[1, 1] > 0 and K[2, 2] == 1.0 and K[1, 0] == 0 and K[2, 0] == 0 \
        and K[2, 1] == 0
    report.check("Camera matrix", k_ok, "3x3, finite, fx>0, fy>0",
                 "Camera matrix is missing, non-finite or malformed. Recalibrate the camera.")
    if k_ok and size_ok:
        report.check("Principal point inside image", 0 < K[0, 2] < w and 0 < K[1, 2] < h,
                     f"cx={K[0, 2]:.1f}, cy={K[1, 2]:.1f}",
                     "Principal point lies outside the image: the calibration is not plausible.")
    d_ok = dist is not None and dist.size in VALID_DIST_LENGTHS and np.all(np.isfinite(dist))
    report.check("Distortion coefficients", d_ok, f"{None if dist is None else dist.size} values",
                 "Distortion coefficients are missing or non-finite. Recalibrate the camera.")
    err = cam.get("reprojection_error_px")
    lim = cfg["calibration"]["camera_intrinsics"]["max_reprojection_error_px"]
    e_ok = isinstance(err, (int, float)) and math.isfinite(err) and 0 <= err <= lim
    report.check("Reprojection error", e_ok, f"{err} px (limit {lim})",
                 f"Camera reprojection error {err} px exceeds the configured limit {lim} px.")
    nmin = cfg["calibration"]["camera_intrinsics"]["min_views"]
    report.check("Number of views", isinstance(cam["num_views"], int) and cam["num_views"] >= nmin,
                 f"{cam['num_views']} (min {nmin})", f"Camera calibration used fewer than {nmin} views.")
    if K is not None and size_ok and d_ok and k_ok:
        report.camera_matrix, report.dist_coeffs, report.image_size = K, dist, (w, h)
    req = cfg["camera"]["resolution"]
    if size_ok and (req["width"], req["height"]) != (w, h):
        msg = (f"config camera.resolution is {req['width']}x{req['height']} but the camera was calibrated at "
               f"{w}x{h}.")
        if cfg["calibration"]["allow_intrinsic_resolution_scaling"] and abs(req["width"] / req["height"] - w / h) < 1e-3:
            report.warnings.append(msg + " Intrinsics will be scaled (allow_intrinsic_resolution_scaling: true).")
        else:
            report.check("Resolution matches configuration", False, msg,
                         msg + " Set the resolution back or recalibrate the camera at the new resolution.")
    report.camera_ok = all(c.passed for c in report.checks)


def validate_laser_section(data: dict[str, Any], cfg: dict[str, Any], report: CalibrationReport) -> None:
    lp = data.get("laser_plane")
    n_before = len(report.checks)
    if not report.check("Laser plane present", isinstance(lp, dict), "present" if isinstance(lp, dict) else "missing",
                        "Laser plane is not calibrated. Run Calibration > 3. Laser Plane."):
        return
    required = ("status", "coefficients", "rms_residual_mm", "num_poses", "camera_section_sha256")
    missing = [k for k in required if k not in lp]
    if not report.check("Laser fields complete", not missing, ", ".join(missing),
                        f"Laser-plane section is incomplete (missing {', '.join(missing)}). Recalibrate the laser plane."):
        return
    report.check("Laser status", lp["status"] == "valid", str(lp["status"]), "Laser plane is not marked valid.")
    coeffs = _finite_matrix(lp["coefficients"], (4,))
    norm_ok = coeffs is not None and abs(np.linalg.norm(coeffs[:3]) - 1.0) < 1e-6 and coeffs[3] <= 0
    report.check("Plane coefficients", norm_ok, "finite, unit normal, d <= 0",
                 "Laser-plane coefficients are non-finite or not normalised. Recalibrate the laser plane.")
    pol = cfg["calibration"]["laser_plane"]
    rms = lp["rms_residual_mm"]
    report.check("Plane fit residual", isinstance(rms, (int, float)) and math.isfinite(rms) and rms <= pol["max_plane_rms_mm"],
                 f"{rms} mm (limit {pol['max_plane_rms_mm']})",
                 f"Laser-plane RMS {rms} mm exceeds the configured limit {pol['max_plane_rms_mm']} mm.")
    report.check("Laser poses", isinstance(lp["num_poses"], int) and lp["num_poses"] >= pol["min_poses"],
                 f"{lp['num_poses']} (min {pol['min_poses']})", f"Laser plane used fewer than {pol['min_poses']} poses.")
    if norm_ok:
        report.check("Plane away from camera", abs(coeffs[3]) >= pol["min_camera_to_plane_distance_mm"],
                     f"{abs(coeffs[3]):.2f} mm",
                     "The laser plane passes through the camera centre; triangulation is degenerate.")
    cam = data.get("camera")
    if isinstance(cam, dict):
        try:
            linked = lp["camera_section_sha256"] == canonical_hash(cam)
        except (TypeError, ValueError):  # e.g. NaN in the camera section
            linked = False
        report.check("Laser plane matches camera calibration", linked, "hash link",
                     "The laser plane does not belong to this camera calibration (camera recalibrated or file "
                     "damaged). Recalibrate the laser plane.")
    if norm_ok:
        report.plane = coeffs
    report.laser_ok = all(c.passed for c in report.checks[n_before:])


def validate_calibration_data(data: dict[str, Any], cfg: dict[str, Any], path: Path | None = None) -> CalibrationReport:
    report = CalibrationReport(path=path, data=data)
    report.check("Schema version", data.get("schema_version") == CALIBRATION_SCHEMA_VERSION,
                 str(data.get("schema_version")),
                 f"Calibration schema {data.get('schema_version')} is not supported (expected "
                 f"{CALIBRATION_SCHEMA_VERSION}). Recalibrate with this software version.")
    report.check("File integrity", integrity_ok(data), "sha256",
                 "The calibration file was edited by hand or is corrupted (integrity hash mismatch). Recalibrate, or "
                 "restore the previous .bak file.")
    hw = data.get("hardware") or {}
    fx = cfg["fixture"]
    report.check("Fixture id matches", hw.get("fixture_id") == fx["fixture_id"],
                 f"file {hw.get('fixture_id')!r} vs config {fx['fixture_id']!r}",
                 "fixture.fixture_id in config.yaml differs from the calibration: the fixture changed. Recalibrate.")
    report.check("Camera tilt setting matches", hw.get("camera_tilt_setting_deg") == fx["camera_tilt_setting_deg"],
                 f"file {hw.get('camera_tilt_setting_deg')} vs config {fx['camera_tilt_setting_deg']}",
                 "fixture.camera_tilt_setting_deg differs from the calibration: the camera was moved. Recalibrate "
                 "camera and laser plane (or set the old angle back if nothing moved).")
    validate_camera_section(data.get("camera"), cfg, report)
    validate_laser_section(data, cfg, report)
    return report


def validate_calibration_file(cfg: dict[str, Any]) -> CalibrationReport:
    path = resolve_project_path(cfg["calibration"]["calibration_file"])
    try:
        data = load_calibration_json(path)
    except (FileNotFoundError, ValueError) as exc:
        report = CalibrationReport(path=path)
        report.check("Calibration file readable", False, str(exc), f"{exc}")
        return report
    return validate_calibration_data(data, cfg, path)


@dataclass
class ModeStatus:
    mode: str
    metric_allowed: bool
    processing_allowed: bool
    experimental_allowed: bool
    report: CalibrationReport | None
    messages: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.mode == MODE_UNCALIBRATED:
            return "UNCALIBRATED MODE (pixel measurements)"
        return "CALIBRATED MODE (mm)" if self.metric_allowed else "CALIBRATED MODE - BLOCKED (calibration invalid)"


def resolve_mode(cfg: dict[str, Any]) -> ModeStatus:
    c = cfg["calibration"]
    if not c["enabled"]:
        return ModeStatus(MODE_UNCALIBRATED, metric_allowed=False, processing_allowed=True,
                          experimental_allowed=bool(c["allow_uncalibrated_metric_estimates"]), report=None,
                          messages=["Uncalibrated mode: results are image-space pixels, not millimetres."])
    report = validate_calibration_file(cfg)
    if report.metric_ready:
        return ModeStatus(MODE_CALIBRATED, True, True, False, report,
                          ["Calibrated mode: calibration passed all checks."])
    msgs = ["Calibrated mode was requested but the calibration is NOT valid. mm measurements are blocked."]
    msgs.extend(report.errors)
    processing = not c["require_valid_calibration"]
    if processing:
        msgs.append("require_valid_calibration is false: pixel-space processing is allowed; mm stays blocked.")
    else:
        msgs.append("require_valid_calibration is true: processing is blocked until the calibration is fixed.")
    return ModeStatus(MODE_CALIBRATED, False, processing, False, report, msgs)


def intrinsics_for_image(report: CalibrationReport, image_size: tuple[int, int],
                         cfg: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    """Intrinsics valid for an image of ``image_size``. Raises ValueError if not justified."""
    if report.camera_matrix is None or report.image_size is None:
        raise ValueError("No valid camera intrinsics loaded.")
    if tuple(image_size) == tuple(report.image_size):
        return report.camera_matrix, report.dist_coeffs
    w0, h0 = report.image_size
    w, h = image_size
    if cfg["calibration"]["allow_intrinsic_resolution_scaling"] and abs(w / h - w0 / h0) < 1e-3:
        return scale_intrinsics(report.camera_matrix, (w0, h0), (w, h)), report.dist_coeffs
    raise ValueError(f"Image is {w}x{h} but the calibration is for {w0}x{h0}. Capture at {w0}x{h0} or recalibrate. "
                     "(Scaling is only allowed when allow_intrinsic_resolution_scaling is true and the aspect ratio "
                     "matches.)")


def flat_plate_check(board_image, laser_image, report: CalibrationReport, spec: CheckerboardSpec, laser_params,
                     cfg: dict[str, Any]) -> dict[str, Any]:
    """Independent check: laser points triangulated with the CALIBRATED laser plane must lie on the board
    plane measured by PnP in a NEW placement. Returns statistics in mm and pass/fail."""
    from calibration.laser_plane_calibration import process_laser_pose  # local import avoids a cycle

    if not report.metric_ready:
        return {"passed": False, "error": "Load a valid calibration first."}
    pol = cfg["calibration"]["laser_plane"]
    pose = process_laser_pose(board_image, laser_image, report.camera_matrix, report.dist_coeffs, report.image_size,
                              spec, laser_params, pol, "flat_plate_check",
                              cfg["measurement"]["min_ray_plane_angle_deg"])
    if pose.stripe_uv is None or pose.board_plane is None or len(pose.stripe_uv) < pol["min_points_per_pose"]:
        return {"passed": False, "error": pose.reason or "Not enough laser points on the board."}
    pts, _ = triangulate_pixels(pose.stripe_uv, report.camera_matrix, report.dist_coeffs, report.plane,
                                cfg["measurement"]["min_ray_plane_angle_deg"])
    pts = pts[np.all(np.isfinite(pts), axis=1)]
    if len(pts) < pol["min_points_per_pose"]:
        return {"passed": False, "error": "Too few laser points could be triangulated with the calibrated plane."}
    dev = point_plane_distances(pts, pose.board_plane)
    limit = cfg["calibration"]["validation"]["max_flat_plate_rms_mm"]
    rms = float(np.sqrt(np.mean(dev ** 2)))
    return {"passed": rms <= limit, "rms_mm": rms, "mean_mm": float(np.mean(dev)),
            "max_abs_mm": float(np.max(np.abs(dev))), "points": int(len(pts)), "limit_mm": limit,
            "board_distance_mm": pose.distance_mm, "pnp_error_px": pose.pnp_error_px}
