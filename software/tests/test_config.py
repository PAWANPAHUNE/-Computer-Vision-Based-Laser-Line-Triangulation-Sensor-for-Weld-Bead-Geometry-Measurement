"""YAML configuration loading, validation and mode selection."""
from __future__ import annotations

import copy

import pytest

from calibration.validation import MODE_CALIBRATED, MODE_UNCALIBRATED, resolve_mode
from tests.conftest import PROJECT, write_yaml
from utils.config_loader import (CONFIG_ENV_VAR, ConfigError, load_config, safe_defaults, save_config,
                                 validate_config)


def test_shipped_config_is_valid_and_never_claims_mm_without_a_valid_calibration():
    rep = load_config(PROJECT / "config" / "config.yaml")
    assert rep.ok, rep.errors
    assert rep.config["camera"]["focal_length_mm"] is None  # unknown optics are never guessed
    if rep.config["calibration"]["enabled"]:
        # Calibrated mode is only allowed when the referenced calibration file really validates.
        mode = resolve_mode(rep.config)
        assert mode.mode == MODE_CALIBRATED, mode.messages


@pytest.mark.parametrize("name", ["config.example.uncalibrated.yaml", "config.example.calibrated.yaml",
                                  "config.example.synthetic_calibrated.yaml"])
def test_example_configs_are_valid(name):
    rep = load_config(PROJECT / "config" / name)
    assert rep.ok, rep.errors


def test_example_modes_match_their_names():
    assert load_config(PROJECT / "config" / "config.example.uncalibrated.yaml").config["calibration"]["enabled"] is False
    assert load_config(PROJECT / "config" / "config.example.calibrated.yaml").config["calibration"]["enabled"] is True


def test_missing_file(tmp_path):
    rep = load_config(tmp_path / "nope.yaml")
    assert not rep.ok and "not found" in rep.errors[0]


def test_yaml_syntax_error_reports_line(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("calibration:\n  enabled: false\n   bad_indent: 1\n")
    rep = load_config(p)
    assert not rep.ok
    assert "YAML syntax error" in rep.errors[0] and "line" in rep.errors[0]


def test_missing_required_keys(tmp_path):
    rep = load_config(write_yaml(tmp_path / "c.yaml", {"camera": {"device_index": 0}}))
    assert not rep.ok
    assert any("calibration.enabled" in e for e in rep.errors)


@pytest.mark.parametrize("key,value,fragment", [
    ("calibration.enabled", "yes", "true or false"),
    ("laser.threshold", -5, ">="),
    ("laser.smoothing_window", 4, "odd"),
    ("camera.resolution.width", 12.5, "whole number"),
    ("measurement.profile_axis", "diagonal", "one of"),
    ("geometry.camera_pitch_deg", 120, "<="),
    ("camera.focal_length_mm", "4mm", "number"),
    ("laser.detection_method", "magic", "one of"),
])
def test_invalid_values_rejected(key, value, fragment):
    cfg = safe_defaults()
    node = cfg
    parts = key.split(".")
    for p in parts[:-1]:
        node = node[p]
    node[parts[-1]] = value
    if key.startswith(("geometry.", "camera.focal")):
        cfg["parameter_sources"][key] = {"source": "measured", "note": ""}
    rep = validate_config(cfg)
    assert not rep.ok
    assert any(key in e and fragment in e for e in rep.errors), rep.errors


def test_value_with_unknown_source_is_rejected():
    cfg = safe_defaults()
    cfg["geometry"]["camera_to_laser_baseline_mm"] = 55.0  # source still 'unknown'
    rep = validate_config(cfg)
    assert any("source is 'unknown'" in e for e in rep.errors)
    cfg["parameter_sources"]["geometry.camera_to_laser_baseline_mm"] = {"source": "measured", "note": "calliper"}
    assert validate_config(cfg).ok


def test_unknown_key_warns_not_fails():
    cfg = safe_defaults()
    cfg["camera"]["colour_mode"] = "fancy"
    rep = validate_config(cfg)
    assert rep.ok and any("colour_mode" in w for w in rep.warnings)


def test_cross_field_depth_range():
    cfg = safe_defaults()
    cfg["measurement"]["max_depth_mm"] = 10.0
    cfg["measurement"]["min_depth_mm"] = 20.0
    assert any("max_depth_mm" in e for e in validate_config(cfg).errors)


def test_save_config_roundtrip_and_backup(tmp_path):
    p = tmp_path / "config.yaml"
    cfg = safe_defaults()
    save_config(cfg, p)
    cfg["laser"]["threshold"] = 42
    save_config(cfg, p)
    assert (tmp_path / "config.yaml.bak").exists()
    assert load_config(p).config["laser"]["threshold"] == 42


def test_save_config_refuses_invalid(tmp_path):
    cfg = safe_defaults()
    cfg["laser"]["threshold"] = 999
    with pytest.raises(ConfigError):
        save_config(cfg, tmp_path / "c.yaml")
    assert not (tmp_path / "c.yaml").exists()


def test_env_var_selects_config(tmp_path, monkeypatch):
    cfg = safe_defaults()
    cfg["laser"]["threshold"] = 77
    p = tmp_path / "other.yaml"
    save_config(cfg, p)
    monkeypatch.setenv(CONFIG_ENV_VAR, str(p))
    assert load_config().config["laser"]["threshold"] == 77


# ------------------------------------------------------------ mode selection
def test_disabled_never_requires_calibration_file(tmp_path):
    cfg = safe_defaults()
    cfg["calibration"]["calibration_file"] = str(tmp_path / "does_not_exist.json")
    mode = resolve_mode(cfg)
    assert mode.mode == MODE_UNCALIBRATED
    assert mode.processing_allowed and not mode.metric_allowed and mode.report is None


def test_enabled_with_missing_file_blocks_and_does_not_fall_back(tmp_path):
    cfg = safe_defaults()
    cfg["calibration"]["enabled"] = True
    cfg["calibration"]["calibration_file"] = str(tmp_path / "missing.json")
    mode = resolve_mode(cfg)
    assert mode.mode == MODE_CALIBRATED          # never silently switches to uncalibrated
    assert not mode.metric_allowed
    assert not mode.processing_allowed           # require_valid_calibration: true
    assert "BLOCKED" in mode.label
    assert any("not found" in m for m in mode.messages)


def test_require_valid_false_allows_pixel_processing_only(tmp_path):
    cfg = safe_defaults()
    cfg["calibration"]["enabled"] = True
    cfg["calibration"]["require_valid_calibration"] = False
    cfg["calibration"]["calibration_file"] = str(tmp_path / "missing.json")
    mode = resolve_mode(cfg)
    assert mode.mode == MODE_CALIBRATED and mode.processing_allowed and not mode.metric_allowed


def test_valid_calibration_enables_metric(calibrated_setup):
    cfg, _ = calibrated_setup
    mode = resolve_mode(cfg)
    assert mode.mode == MODE_CALIBRATED and mode.metric_allowed, mode.messages


def test_flag_change_switches_mode(calibrated_setup):
    cfg, _ = calibrated_setup
    assert resolve_mode(cfg).mode == MODE_CALIBRATED
    cfg2 = copy.deepcopy(cfg)
    cfg2["calibration"]["enabled"] = False
    assert resolve_mode(cfg2).mode == MODE_UNCALIBRATED
