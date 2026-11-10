"""End-to-end measurement of one image, honouring the operating mode.

Outputs are tagged so that pixels are never presented as millimetres:
* ``pixel``                 - always computed (image space, px);
* ``metric``                - only in CALIBRATED mode with a calibration that passed every check
                              AND measurement confidence >= ``measurement.minimum_confidence``;
* ``experimental_estimates`` - only in UNCALIBRATED mode with
                              ``allow_uncalibrated_metric_estimates: true``; always labelled EXPERIMENTAL.

One image = one laser line = ONE cross-section of the bead. A seam needs many profiles plus robot
position data to place them along the seam.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np

from calibration.nominal_model import build_nominal_model, missing_nominal_parameters
from calibration.triangulation import DegeneratePlaneError, points_to_plane_profile, triangulate_pixels
from calibration.validation import MODE_CALIBRATED, ModeStatus, intrinsics_for_image
from version import SOFTWARE_VERSION
from vision.laser_detection import LaserDetectionParams, StripeResult, detect_laser_stripe
from vision.profile_extraction import PixelProfile, pixel_profile
from vision.weld_measurement import MeasurementSettings, WeldMeasurement, measure_profile


@dataclass
class ReferenceScale:
    """User-supplied reference for EXPERIMENTAL mm estimates (uncalibrated mode).

    ``width_mm_per_px``: from a known length lying along the laser line, at the same distance.
    ``height_mm_per_px``: from a known step height (e.g. a gauge block) measured as stripe displacement.
    """
    width_mm_per_px: float | None = None
    height_mm_per_px: float | None = None
    description: str = ""


@dataclass
class MeasurementResult:
    timestamp_utc: str
    mode_label: str
    mode: str
    image_size: tuple[int, int]
    stripe: StripeResult
    profile: PixelProfile
    pixel: WeldMeasurement
    metric: dict[str, Any] | None = None
    metric_points: np.ndarray | None = None      # (N, 3) camera-frame mm, NaN invalid
    metric_s: np.ndarray | None = None
    metric_h: np.ndarray | None = None
    metric_reasons: np.ndarray | None = None
    metric_height_curve: np.ndarray | None = None  # mm above the base reference, per profile sample
    experimental_estimates: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blocked_reason: str | None = None
    calibration_fingerprint: str | None = None
    settings: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "software_version": SOFTWARE_VERSION,
            "timestamp_utc": self.timestamp_utc,
            "mode": self.mode,
            "mode_label": self.mode_label,
            "image_size": {"width": self.image_size[0], "height": self.image_size[1]},
            "note": "One image gives ONE cross-section of the bead.",
            "detection": self.stripe.summary(),
            "pixel_measurement": {
                "units": "px",
                "meaning": "Image-space measurement. width_px = bead extent along the laser line; "
                           "height_px = stripe displacement caused by the bead. These are NOT millimetres.",
                **self.pixel.to_dict(),
            },
            "metric_measurement": self.metric,
            "experimental_estimates": self.experimental_estimates,
            "warnings": self.warnings,
            "metric_blocked_reason": self.blocked_reason,
            "calibration_fingerprint": self.calibration_fingerprint,
            "settings": self.settings,
        }


def _settings_px(cfg: dict[str, Any], direction: str) -> MeasurementSettings:
    m = cfg["measurement"]
    return MeasurementSettings(units="px", min_bead_height=m["min_bead_height_px"],
                               boundary_fraction=m["boundary_fraction"], reference_surface=m["reference_surface"],
                               bead_direction=direction, peak_smoothing=int(m.get("peak_smoothing_points", 1)))


def _settings_mm(cfg: dict[str, Any]) -> MeasurementSettings:
    m = cfg["measurement"]
    return MeasurementSettings(units="mm", min_bead_height=m["min_bead_height_mm"],
                               boundary_fraction=m["boundary_fraction"], reference_surface=m["reference_surface"],
                               bead_direction="positive", peak_smoothing=int(m.get("peak_smoothing_points", 1)))


def _metric_from_points(uv: np.ndarray, conf: np.ndarray, K, dist, plane, cfg, label: str):
    m = cfg["measurement"]
    pts, reasons = triangulate_pixels(uv, K, dist, plane, m["min_ray_plane_angle_deg"],
                                      (m["min_depth_mm"], m["max_depth_mm"]))
    prof = points_to_plane_profile(pts, plane)
    meas = measure_profile(prof.s, prof.h, _settings_mm(cfg), conf)
    counts = {str(k): int(v) for k, v in zip(*np.unique(reasons.astype(str), return_counts=True))}
    return pts, prof, meas, counts, reasons


def run_measurement(image_bgr: np.ndarray, cfg: dict[str, Any], mode: ModeStatus,
                    laser_params: LaserDetectionParams | None = None, profile_axis: str | None = None,
                    bead_direction: str | None = None, reference: ReferenceScale | None = None) -> MeasurementResult:
    if not mode.processing_allowed:
        raise PermissionError("Processing is blocked: " + " ".join(mode.messages))
    params = laser_params or LaserDetectionParams.from_config(cfg["laser"])
    axis = profile_axis or cfg["measurement"]["profile_axis"]
    direction = bead_direction or cfg["measurement"]["bead_direction"]
    h, w = image_bgr.shape[:2]
    stripe = detect_laser_stripe(image_bgr, params, axis=axis)
    prof = pixel_profile(stripe)
    pix = measure_profile(prof.x, prof.y, _settings_px(cfg, direction), prof.confidence)
    result = MeasurementResult(
        timestamp_utc=datetime.now(timezone.utc).replace(microsecond=0).isoformat(), mode_label=mode.label,
        mode=mode.mode, image_size=(w, h), stripe=stripe, profile=prof, pixel=pix,
        warnings=list(stripe.warnings) + list(pix.warnings),
        settings={"laser": params.__dict__.copy(), "profile_axis_requested": axis, "profile_axis_used": stripe.axis,
                  "bead_direction": direction, "measurement": dict(cfg["measurement"])})
    min_conf = cfg["measurement"]["minimum_confidence"]
    if stripe.overall_confidence < min_conf:
        result.warnings.append(f"Laser detection confidence {stripe.overall_confidence:.2f} is below the minimum "
                               f"{min_conf}. The stripe cannot be detected reliably.")
    uv = prof.image_uv()

    if mode.mode == MODE_CALIBRATED:
        if not mode.metric_allowed:
            result.blocked_reason = "Calibration invalid: " + "; ".join(mode.report.errors if mode.report else [])
            return result
        rep = mode.report
        result.calibration_fingerprint = rep.fingerprint
        try:
            K, dist = intrinsics_for_image(rep, (w, h), cfg)
        except ValueError as exc:
            result.blocked_reason = str(exc)
            return result
        try:
            pts, pp, meas, counts, reasons = _metric_from_points(uv, prof.confidence, K, dist, rep.plane, cfg,
                                                                 "calibrated")
        except DegeneratePlaneError as exc:
            result.blocked_reason = f"Triangulation failed: {exc}"
            return result
        result.metric_points, result.metric_s, result.metric_h = pts, pp.s, pp.h
        result.metric_reasons = reasons
        result.metric_height_curve = np.asarray(meas.height_curve if meas.height_curve else
                                                np.full(len(pts), np.nan), dtype=float)
        validated = meas.status == "ok" and meas.confidence >= min_conf and stripe.overall_confidence >= min_conf
        lp = rep.data.get("laser_plane", {})
        dr = lp.get("depth_range_mm")
        zs = pts[np.all(np.isfinite(pts), axis=1), 2]
        if dr and zs.size and (zs.min() < dr[0] - 0.25 * (dr[1] - dr[0]) or zs.max() > dr[1] + 0.25 * (dr[1] - dr[0])):
            result.warnings.append(f"Measured depths {zs.min():.0f}-{zs.max():.0f} mm extend beyond the laser-plane "
                                   f"calibration range {dr[0]:.0f}-{dr[1]:.0f} mm (extrapolation).")
        result.metric = {
            "units": "mm",
            "validated": bool(validated),
            "status": meas.status if validated or meas.status != "ok" else "low_confidence",
            "basis": "Calibrated camera intrinsics + calibrated laser plane (ray-plane triangulation).",
            "height_definition": "Largest perpendicular distance from the base reference line inside the laser "
                                 "plane. Equals reinforcement height when the laser plane is perpendicular to the "
                                 "base metal.",
            "triangulation_point_status": counts,
            **meas.to_dict(),
        }
        result.warnings.extend(f"[mm] {w_}" for w_ in meas.warnings)
        if not validated:
            result.blocked_reason = (f"mm result withheld: status {meas.status}, measurement confidence "
                                     f"{meas.confidence:.2f}, detection confidence {stripe.overall_confidence:.2f} "
                                     f"(minimum {min_conf}).")
        return result

    # ---------------- uncalibrated mode
    result.blocked_reason = "Uncalibrated mode: no validated mm measurements."
    if not mode.experimental_allowed:
        return result
    if reference and pix.status == "ok":
        est: dict[str, Any] = {
            "label": "EXPERIMENTAL ESTIMATE - reference scale (not a calibrated measurement)",
            "method": "pixel value x user-supplied mm-per-pixel factor",
            "assumptions": [
                "The reference was imaged at the same distance and in the same place as the bead.",
                "Width scale is valid only along the laser line, near the reference, for a flat surface.",
                "Height scale is a local linear approximation of the triangulation from a known step at the same "
                "working distance; it is not valid for other distances or large heights.",
                "Perspective and lens distortion are ignored; a single global scale is NOT valid across the image.",
            ],
            "reference": reference.description,
            "width_mm": pix.width * reference.width_mm_per_px if reference.width_mm_per_px else None,
            "height_mm": pix.height * reference.height_mm_per_px if reference.height_mm_per_px else None,
        }
        result.experimental_estimates.append(est)
    missing = missing_nominal_parameters(cfg)
    if missing:
        result.experimental_estimates.append({
            "label": "EXPERIMENTAL ESTIMATE - nominal geometry (not available)",
            "available": False,
            "reason": "Missing parameters: " + ", ".join(missing)})
    else:
        model = build_nominal_model(cfg, (w, h))
        try:
            _, _, meas, counts, _ = _metric_from_points(uv, prof.confidence, model.camera_matrix,
                                                        model.dist_coeffs, model.laser_plane_camera, cfg, "nominal")
            result.experimental_estimates.append({
                "label": "EXPERIMENTAL ESTIMATE - nominal geometry model (not calibrated)",
                "available": True,
                "assumptions": model.assumptions,
                "width_mm": meas.width, "height_mm": meas.height, "status": meas.status,
                "confidence": meas.confidence, "triangulation_point_status": counts})
        except DegeneratePlaneError as exc:
            result.experimental_estimates.append({"label": "EXPERIMENTAL ESTIMATE - nominal geometry model",
                                                  "available": False, "reason": str(exc)})
    return result
