"""Calibration.md and README must describe the implemented software exactly."""
from __future__ import annotations

import re

import pytest

import ui_labels as L
from tests.conftest import PROJECT
from utils.config_loader import DEFAULT_CONFIG, load_config

CAL = (PROJECT / "Calibration.md").read_text(encoding="utf-8")
README = (PROJECT / "README.md").read_text(encoding="utf-8")
APP = (PROJECT / "app.py").read_text(encoding="utf-8")
LABELS = set(L.ALL.values())


def test_every_quoted_ui_label_exists():
    quoted = set(re.findall(r'\*\*"([^"]+)"\*\*', CAL))
    assert quoted, "Calibration.md should quote UI labels as **\"Label\"**"
    missing = [q for q in quoted if q not in LABELS and q not in APP]
    assert not missing, f"Calibration.md mentions labels that do not exist in the app: {missing}"


def test_key_labels_are_documented():
    for label in (L.RUN_CAMERA_CAL, L.SAVE_CAMERA_CAL, L.FIT_PLANE, L.SAVE_LASER_CAL, L.ADD_POSE,
                  L.CAPTURE_VIEW, L.VALIDATE_FILE, L.RUN_FLAT, L.RELOAD_CONFIG, L.STEP_INTRINSICS, L.STEP_LASER):
        assert f'**"{label}"**' in CAL, label


def _key_exists(dotted: str) -> bool:
    node = DEFAULT_CONFIG
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


@pytest.mark.parametrize("doc", ["Calibration.md", "README.md"])
def test_documented_yaml_keys_exist(doc):
    text = (PROJECT / doc).read_text(encoding="utf-8")
    keys = set(re.findall(r"`((?:calibration|camera|geometry|laser|measurement|output|fixture)\.[a-z_.]+)`", text))
    assert keys
    bad = [k for k in keys if not _key_exists(k)]
    assert not bad, f"{doc} mentions config keys that do not exist: {bad}"


@pytest.mark.parametrize("doc", ["Calibration.md", "README.md"])
def test_documented_project_files_exist(doc):
    text = (PROJECT / doc).read_text(encoding="utf-8")
    paths = set(re.findall(r"`((?:config|assets|scripts|calibration|vision|utils)/[A-Za-z0-9_./*-]+)`", text))
    paths |= {p for p in re.findall(r"python (scripts/[a-z_]+\.py)", text)}
    for p in paths:
        if "*" in p:
            continue
        assert (PROJECT / p.rstrip("/")).exists(), f"{doc}: {p} does not exist"


def test_commands_match_files():
    for text in (CAL, README):
        assert "streamlit run app.py" in text
        assert "python -m pytest" in text
    assert (PROJECT / "app.py").exists()


def test_checkerboard_and_policy_numbers_match_config():
    # Calibration.md documents the shipped defaults (the user's own config.yaml may differ).
    cfg = load_config(PROJECT / "config" / "config.example.uncalibrated.yaml").config
    cb = cfg["calibration"]["checkerboard"]
    assert f"{cb['inner_corners_cols']} x {cb['inner_corners_rows']} inner corners" in CAL
    assert f"{cb['inner_corners_cols'] + 1} x {cb['inner_corners_rows'] + 1} squares" in CAL
    assert f"squares of **{cb['square_size_mm']:g} mm**" in CAL
    ci = cfg["calibration"]["camera_intrinsics"]
    assert f"minimum {ci['min_views']}, target {ci['recommended_views']}" in CAL
    assert f"at least {ci['min_coverage_cells']} of 9" in CAL
    assert f"at least {ci['min_tilt_range_deg']:g}°" in CAL
    assert f"at most {ci['max_reprojection_error_px']:.1f} px" in CAL
    lp = cfg["calibration"]["laser_plane"]
    assert f"at least {lp['min_poses']}" in CAL
    assert f"at least {lp['min_pose_spread_mm']:g} mm" in CAL
    assert f"at most {lp['max_plane_rms_mm']:g} mm" in CAL
    assert f"limit {cfg['calibration']['validation']['max_flat_plate_rms_mm']:g} mm" in CAL
    assert f"({cfg['measurement']['minimum_confidence']:g})" in CAL


def test_supplied_board_matches_default_config():
    cfg = load_config(PROJECT / "config" / "config.example.uncalibrated.yaml").config
    cb = cfg["calibration"]["checkerboard"]
    name = f"checkerboard_{cb['inner_corners_cols']}x{cb['inner_corners_rows']}_{cb['square_size_mm']:g}mm.pdf"
    assert (PROJECT / "assets" / name).exists()
    assert f"`assets/{name}`" in CAL


def test_mode_strings_in_docs_match_app():
    from calibration.validation import ModeStatus
    for mode, metric in (("uncalibrated", False), ("calibrated", True), ("calibrated", False)):
        label = ModeStatus(mode, metric, True, False, None).label
        assert label in CAL, label
