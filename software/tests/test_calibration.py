"""Camera + laser-plane calibration, calibration file validity checks, flat-plate check."""
from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from calibration.calibration_file import camera_section, new_calibration, save_calibration, with_integrity
from calibration.camera_calibration import calibrate_intrinsics, detect_view
from calibration.laser_plane_calibration import fit_laser_plane, process_laser_pose
from calibration.validation import (flat_plate_check, resolve_mode, validate_calibration_data,
                                    validate_calibration_file)
from synthetic.demo import DEMO_SPEC, demo_rig
from synthetic.scene import look_at_pose, render_board_image
from tests.conftest import edit_json
from vision.laser_detection import LaserDetectionParams


def test_intrinsics_recovered(synth_cal):
    intr, rig = synth_cal["intrinsics"], synth_cal["rig"]
    assert intr.rms_px < 0.5
    assert intr.camera_matrix[0, 0] == pytest.approx(rig.focal_px, rel=0.005)
    assert intr.camera_matrix[0, 2] == pytest.approx(rig.K[0, 2], abs=3.0)
    assert intr.dist_coeffs[0] == pytest.approx(rig.dist_coeffs[0], abs=0.02)
    assert intr.coverage_cells == 9


def test_laser_plane_recovered(synth_cal):
    assert synth_cal["plane_angle_error_deg"] < 0.2
    assert synth_cal["plane_distance_error_mm"] < 0.5
    assert synth_cal["laser"].rms_mm < 0.1


def test_fix_k3_option_holds_third_radial_term_at_zero(synth_cal, cfg):
    policy = dict(cfg["calibration"]["camera_intrinsics"], fix_k3=True)
    res = calibrate_intrinsics(synth_cal["views"], DEMO_SPEC, policy)
    assert res.dist_coeffs[4] == 0.0
    assert res.camera_matrix[0, 0] == pytest.approx(synth_cal["rig"].focal_px, rel=0.01)


def test_fix_k3_is_a_known_config_setting():
    from utils.config_loader import validate_config
    rep = validate_config({"calibration": {"enabled": False, "calibration_file": "x.json",
                                           "require_valid_calibration": True,
                                           "allow_uncalibrated_metric_estimates": False,
                                           "camera_intrinsics": {"fix_k3": True}}})
    assert rep.config["calibration"]["camera_intrinsics"]["fix_k3"] is True
    assert not any("fix_k3" in w for w in rep.warnings)


def test_too_few_views_rejected(synth_cal, cfg):
    views = synth_cal["views"][:5]
    res = calibrate_intrinsics(views, DEMO_SPEC, cfg["calibration"]["camera_intrinsics"])
    assert not res.ok and res.needs_more_views and "at least" in res.errors[0]


def test_poor_coverage_rejected(cfg):
    rig = demo_rig()
    views = []
    for k in range(12):  # all views centred, same tilt: poor coverage and tilt variety
        rv, tv = look_at_pose(200 + 3 * k, 0.5, 0.0, DEMO_SPEC)
        views.append(detect_view(render_board_image(rig, DEMO_SPEC, rv, tv, seed=k), DEMO_SPEC, f"v{k}"))
    res = calibrate_intrinsics(views, DEMO_SPEC, cfg["calibration"]["camera_intrinsics"])
    assert not res.ok
    assert any("tilt" in e for e in res.errors)


def test_view_without_board_rejected_with_message():
    v = detect_view(np.full((400, 600, 3), 128, np.uint8), DEMO_SPEC, "blank")
    assert not v.ok and "not found" in v.reason


def test_laser_plane_needs_distinct_poses(synth_cal, cfg):
    intr, rig = synth_cal["intrinsics"], synth_cal["rig"]
    pol = cfg["calibration"]["laser_plane"]
    params = LaserDetectionParams()
    poses = []
    rv, tv = look_at_pose(160, 0, 0, DEMO_SPEC)
    for k in range(3):  # same placement three times
        off = render_board_image(rig, DEMO_SPEC, rv, tv, False, seed=k)
        on = render_board_image(rig, DEMO_SPEC, rv, tv, True, seed=10 + k)
        poses.append(process_laser_pose(off, on, intr.camera_matrix, intr.dist_coeffs, intr.image_size, DEMO_SPEC,
                                        params, pol, f"p{k}"))
    assert all(p.ok for p in poses)
    res = fit_laser_plane(poses, pol)
    assert not res.ok and any("apart" in e for e in res.errors)


def test_laser_plane_needs_min_poses(synth_cal, cfg):
    res = fit_laser_plane(synth_cal["poses"][:2], cfg["calibration"]["laser_plane"])
    assert not res.ok and "at least" in res.errors[0]


def test_pose_rejected_without_laser(synth_cal, cfg):
    intr, rig = synth_cal["intrinsics"], synth_cal["rig"]
    rv, tv = look_at_pose(160, 0, 0, DEMO_SPEC)
    off = render_board_image(rig, DEMO_SPEC, rv, tv, False)
    pose = process_laser_pose(off, off, intr.camera_matrix, intr.dist_coeffs, intr.image_size, DEMO_SPEC,
                              LaserDetectionParams(), cfg["calibration"]["laser_plane"], "nolaser")
    assert not pose.ok and "laser points" in pose.reason


def test_pose_rejected_on_resolution_mismatch(synth_cal, cfg):
    intr = synth_cal["intrinsics"]
    img = np.zeros((400, 640, 3), np.uint8)
    pose = process_laser_pose(img, img, intr.camera_matrix, intr.dist_coeffs, intr.image_size, DEMO_SPEC,
                              LaserDetectionParams(), cfg["calibration"]["laser_plane"], "small")
    assert not pose.ok and "calibrated at" in pose.reason


# ------------------------------------------------------------ calibration file
def test_file_roundtrip_valid(calibrated_setup):
    cfg, path = calibrated_setup
    rep = validate_calibration_file(cfg)
    assert rep.metric_ready, rep.errors
    data = json.loads(path.read_text())
    assert np.isclose(np.linalg.norm(data["laser_plane"]["coefficients"][:3]), 1.0)
    assert data["software"]["version"] and data["camera"]["checkerboard"]["square_size_mm"] == 12.0


def test_existing_file_is_not_trusted_blindly(calibrated_setup):
    cfg, path = calibrated_setup
    edit_json(path, lambda d: d["laser_plane"].__setitem__("rms_residual_mm", 0.0001))  # hand edit
    rep = validate_calibration_file(cfg)
    assert not rep.metric_ready and any("integrity" in e for e in rep.errors)


@pytest.mark.parametrize("mutate,fragment", [
    (lambda d: d["camera"].__setitem__("camera_matrix", [[1, 0], [0, 1]]), "Camera matrix"),
    (lambda d: d["camera"].__setitem__("dist_coeffs", [float("nan")] * 5), "Distortion"),
    (lambda d: d["laser_plane"].__setitem__("coefficients", [0, 0, 2, -100]), "normalised"),
    (lambda d: d.__setitem__("laser_plane", None), "Laser plane is not calibrated"),
    (lambda d: d["camera"].pop("reprojection_error_px"), "incomplete"),
    (lambda d: d.__setitem__("schema_version", 99), "schema"),
])
def test_invalid_contents_block_metric(synth_cal, cfg, mutate, fragment):
    c = copy.deepcopy(synth_cal["cfg"])
    data = copy.deepcopy(synth_cal["calibration_data"])
    mutate(data)
    try:
        data = with_integrity(data)  # even with a fresh integrity hash, contents are re-checked
    except ValueError:
        pass  # NaN cannot be written as strict JSON; the raw dict is still validated
    rep = validate_calibration_data(data, c)
    assert not rep.metric_ready
    assert any(fragment.lower() in e.lower() for e in rep.errors), rep.errors


def test_malformed_json_blocks(calibrated_setup):
    cfg, path = calibrated_setup
    path.write_text("{ not json")
    mode = resolve_mode(cfg)
    assert not mode.metric_allowed and any("not valid JSON" in m for m in mode.messages)


def test_resolution_change_invalidates(calibrated_setup):
    cfg, _ = calibrated_setup
    cfg["camera"]["resolution"] = {"width": 1920, "height": 1080}
    rep = validate_calibration_file(cfg)
    assert not rep.metric_ready and any("1920x1080" in e for e in rep.errors)


def test_resolution_scaling_only_when_allowed_and_same_aspect(calibrated_setup):
    cfg, _ = calibrated_setup
    cfg["camera"]["resolution"] = {"width": 640, "height": 400}
    cfg["calibration"]["allow_intrinsic_resolution_scaling"] = True
    rep = validate_calibration_file(cfg)
    assert rep.metric_ready and rep.warnings
    cfg["camera"]["resolution"] = {"width": 640, "height": 480}  # different aspect: never scaled
    assert not validate_calibration_file(cfg).metric_ready


def test_fixture_change_invalidates(calibrated_setup):
    cfg, _ = calibrated_setup
    cfg["fixture"]["camera_tilt_setting_deg"] = 30.0  # camera was re-aimed
    rep = validate_calibration_file(cfg)
    assert not rep.metric_ready and any("camera was moved" in e for e in rep.errors)


def test_new_camera_calibration_invalidates_old_laser_plane(synth_cal, tmp_path):
    cfg = copy.deepcopy(synth_cal["cfg"])
    data = copy.deepcopy(synth_cal["calibration_data"])
    data["camera"]["reprojection_error_px"] = 0.2  # a different camera calibration
    rep = validate_calibration_data(with_integrity(data), cfg)
    assert not rep.laser_ok and any("does not belong to this camera calibration" in e for e in rep.errors)


def test_camera_only_file_is_not_metric_ready(synth_cal, tmp_path):
    cfg = copy.deepcopy(synth_cal["cfg"])
    data = new_calibration(cfg)
    data["camera"] = camera_section(synth_cal["intrinsics"])
    path = save_calibration(data, tmp_path / "cal.json")
    cfg["calibration"]["calibration_file"] = str(path)
    rep = validate_calibration_file(cfg)
    assert rep.camera_ok and not rep.laser_ok and not rep.metric_ready


def test_save_keeps_backup(synth_cal, tmp_path):
    p = tmp_path / "cal.json"
    save_calibration(copy.deepcopy(synth_cal["calibration_data"]), p)
    save_calibration(copy.deepcopy(synth_cal["calibration_data"]), p)
    assert list(tmp_path.glob("cal.*.bak"))


def test_flat_plate_check_passes_on_new_pose(calibrated_setup, synth_cal):
    cfg, _ = calibrated_setup
    rep = validate_calibration_file(cfg)
    rig = synth_cal["rig"]
    rv, tv = look_at_pose(175, -8, 6, DEMO_SPEC)  # a placement not used for calibration
    off = render_board_image(rig, DEMO_SPEC, rv, tv, False, seed=300)
    on = render_board_image(rig, DEMO_SPEC, rv, tv, True, seed=301)
    out = flat_plate_check(off, on, rep, DEMO_SPEC, LaserDetectionParams(), cfg)
    assert out["passed"], out
    assert out["rms_mm"] < 0.15
