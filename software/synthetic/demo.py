"""Synthetic demonstration runs with known ground truth.

These numbers verify that the software is self-consistent. They are NOT the accuracy of the
real camera + laser + fixture, which must be measured with real reference parts (Calibration.md, Part G).
"""
from __future__ import annotations

import copy
import math
from typing import Any

import numpy as np

from calibration.calibration_file import camera_section, laser_section, new_calibration, with_integrity
from calibration.camera_calibration import calibrate_intrinsics, detect_view
from calibration.checkerboard import CheckerboardSpec
from calibration.laser_plane_calibration import fit_laser_plane, process_laser_pose
from calibration.validation import resolve_mode, validate_calibration_data
from synthetic.scene import BeadSpec, SyntheticRig, look_at_pose, render_board_image, render_weld_image
from utils.config_loader import safe_defaults
from vision.laser_detection import LaserDetectionParams
from vision.pipeline import run_measurement

DEMO_SPEC = CheckerboardSpec(9, 6, 12.0)
SYNTHETIC_FIXTURE_ID = "synthetic_rig"


def demo_rig() -> SyntheticRig:
    return SyntheticRig(width=1280, height=800, focal_px=1000.0, baseline_mm=55.0, pitch_deg=20.0,
                        dist_coeffs=np.array([-0.12, 0.05, 0.0005, -0.0004, 0.0]))


def demo_config(spec: CheckerboardSpec = DEMO_SPEC) -> dict[str, Any]:
    cfg = safe_defaults()
    cfg["calibration"]["checkerboard"] = spec.to_dict()
    cfg["camera"]["resolution"] = {"width": 1280, "height": 800}
    cfg["fixture"]["fixture_id"] = SYNTHETIC_FIXTURE_ID
    cfg["fixture"]["camera_tilt_setting_deg"] = 20.0
    return cfg


INTRINSIC_POSES = [  # (distance mm, tilt about x deg, tilt about y deg, shift x mm, shift y mm)
    (200, 0, 0, 0, 0), (180, 25, 0, 0, 0), (180, -25, 0, 0, 0), (180, 0, 25, 0, 0), (180, 0, -25, 0, 0),
    (230, 15, 15, -45, -30), (230, -15, 15, 45, -30), (230, 15, -15, -45, 30), (230, -15, -15, 45, 30),
    (260, 10, -20, -60, 0), (260, -10, 20, 60, 0), (260, 20, 0, 0, -45), (260, -20, 0, 0, 45),
    (160, 10, 10, 0, 0), (300, -5, 30, 0, 0), (300, 30, -5, 0, 0),
]
LASER_POSES = [(135, 10, 0), (160, -10, 8), (185, 5, -10), (215, -5, 12)]  # distance, tilt x, tilt y


def synthetic_calibration(rig: SyntheticRig | None = None, spec: CheckerboardSpec = DEMO_SPEC,
                          seed: int = 0) -> dict[str, Any]:
    """Run camera + laser-plane calibration on rendered images. Returns results and truth comparison."""
    rig = rig or demo_rig()
    cfg = demo_config(spec)
    views = []
    for k, (d, tx, ty, sx, sy) in enumerate(INTRINSIC_POSES):
        rvec, tvec = look_at_pose(d, tx, ty, spec, (sx, sy))
        img = render_board_image(rig, spec, rvec, tvec, seed=seed + k)
        views.append(detect_view(img, spec, f"view_{k:02d}"))
    intr = calibrate_intrinsics(views, spec, cfg["calibration"]["camera_intrinsics"])
    out: dict[str, Any] = {"rig": rig, "cfg": cfg, "views": views, "intrinsics": intr}
    if not intr.ok:
        return out
    params = LaserDetectionParams.from_config(cfg["laser"])
    poses = []
    for k, (d, tx, ty) in enumerate(LASER_POSES):
        rvec, tvec = look_at_pose(d, tx, ty, spec)
        off = render_board_image(rig, spec, rvec, tvec, laser_on=False, seed=100 + k)
        on = render_board_image(rig, spec, rvec, tvec, laser_on=True, seed=200 + k)
        poses.append(process_laser_pose(off, on, intr.camera_matrix, intr.dist_coeffs, intr.image_size, spec, params,
                                        cfg["calibration"]["laser_plane"], f"pose_{k + 1}"))
    lp = fit_laser_plane(poses, cfg["calibration"]["laser_plane"])
    out.update({"poses": poses, "laser": lp})
    if lp.ok:
        data = new_calibration(cfg)
        data["camera"] = camera_section(intr)
        data["laser_plane"] = laser_section(lp, spec, data["camera"])
        data = with_integrity(data)
        out["calibration_data"] = data
        truth = rig.laser_plane_camera
        out["plane_angle_error_deg"] = math.degrees(math.acos(min(1.0, abs(float(lp.plane[:3] @ truth[:3])))))
        out["plane_distance_error_mm"] = abs(abs(lp.plane[3]) - abs(truth[3]))
        out["fx_error_pct"] = 100 * abs(intr.camera_matrix[0, 0] - rig.focal_px) / rig.focal_px
    return out


def calibrated_mode_for(data: dict[str, Any], cfg: dict[str, Any]):
    """Mode status for in-memory calibration data (used by tests/demo; the app reads the file)."""
    from calibration.validation import MODE_CALIBRATED, ModeStatus
    report = validate_calibration_data(data, cfg)
    return ModeStatus(MODE_CALIBRATED, report.metric_ready, True, False, report, list(report.errors))


def detection_scenarios() -> list[dict[str, Any]]:
    return [
        {"name": "clean", "kw": {}},
        {"name": "noisy", "kw": {"noise": 12.0}},
        {"name": "weak laser", "kw": {"intensity": 60.0}},
        {"name": "very bright (saturated)", "kw": {"intensity": 400.0}},
        {"name": "gaps in stripe", "kw": {"gaps_mm": [(-30, -24), (15, 18)]}},
        {"name": "reflection blob", "kw": {"reflection": True}},
        {"name": "bead off-centre", "bead": {"center_mm": -25.0}},
        {"name": "tilted base plate", "bead": {"base_slope": 0.15}},
    ]


def run_detection_demo(rig: SyntheticRig | None = None) -> list[dict[str, Any]]:
    rig = rig or SyntheticRig()
    rows = []
    for sc in detection_scenarios():
        bead = BeadSpec(**{"width_mm": 8.0, "height_mm": 2.0, "center_mm": 5.0, **sc.get("bead", {})})
        img, truth = render_weld_image(rig, bead, seed=7, **sc.get("kw", {}))
        cfg = safe_defaults()
        cfg["calibration"]["allow_uncalibrated_metric_estimates"] = True
        g = rig.config_geometry()
        cfg["camera"].update(g["camera"])
        cfg["geometry"].update(g["geometry"])
        res = run_measurement(img, cfg, resolve_mode(cfg))
        est = next((e for e in res.experimental_estimates if e.get("available")), {})
        rows.append({"scenario": sc["name"], "status": res.pixel.status,
                     "detection_conf": round(res.stripe.overall_confidence, 3),
                     "width_px": res.pixel.width, "width_px_true": truth["width_px"],
                     "height_px": res.pixel.height, "height_px_true": truth["height_px"],
                     "nominal_width_mm": est.get("width_mm"), "nominal_height_mm": est.get("height_mm"),
                     "true_width_mm": bead.width_mm, "true_height_mm": bead.height_mm,
                     "warnings": res.warnings})
    return rows


def run_calibrated_demo(seed: int = 0) -> dict[str, Any]:
    cal = synthetic_calibration(seed=seed)
    if "calibration_data" not in cal:
        return {"ok": False, "calibration": cal}
    rig, cfg = cal["rig"], copy.deepcopy(cal["cfg"])
    cfg["calibration"]["enabled"] = True
    mode = calibrated_mode_for(cal["calibration_data"], cfg)
    rows = []
    for bead in (BeadSpec(8.0, 2.0, 5.0, 160.0), BeadSpec(6.0, 1.2, -10.0, 150.0), BeadSpec(10.0, 3.0, 0.0, 175.0)):
        img, _ = render_weld_image(rig, bead, seed=11)
        res = run_measurement(img, cfg, mode)
        m = res.metric or {}
        rows.append({"true_width_mm": bead.width_mm, "true_height_mm": bead.height_mm,
                     "width_mm": m.get("width"), "height_mm": m.get("height"), "validated": m.get("validated"),
                     "confidence": m.get("confidence")})
    return {"ok": True, "calibration": cal, "measurements": rows, "mode": mode}
