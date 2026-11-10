"""Run the real Streamlit script headlessly (streamlit.testing) in both modes."""
from __future__ import annotations

import copy

import pytest
from streamlit.testing.v1 import AppTest

import ui_labels as L
from calibration.calibration_file import save_calibration
from synthetic.demo import demo_rig
from synthetic.scene import BeadSpec, render_weld_image
from tests.conftest import PROJECT
from utils.config_loader import CONFIG_ENV_VAR, safe_defaults, save_config

APP = str(PROJECT / "app.py")


def run_app(monkeypatch, cfg_path, image=None):
    monkeypatch.setenv(CONFIG_ENV_VAR, str(cfg_path))
    at = AppTest.from_file(APP, default_timeout=120)
    if image is not None:
        at.session_state["image"] = image
        at.session_state["image_name"] = "test"
        at.session_state["detect_requested"] = True
    return at.run()


def texts(at):
    out = []
    for kind in ("info", "success", "error", "warning", "markdown", "caption"):
        out += [e.value for e in getattr(at, kind)]
    out += [e.value for e in at.sidebar.info] + [e.value for e in at.sidebar.success] + [e.value for e in at.sidebar.error]
    return " ".join(str(t) for t in out)


def test_uncalibrated_app_runs_and_shows_pixels(monkeypatch, tmp_path):
    p = save_config(safe_defaults(), tmp_path / "config.yaml")
    img, _ = render_weld_image(demo_rig(), BeadSpec(8, 2, 5, 160), seed=1)
    at = run_app(monkeypatch, p, img)
    assert not at.exception
    assert [t.label for t in at.tabs] == [L.TAB_MEASURE, L.TAB_PARAMETERS, L.TAB_CALIBRATION]
    assert "UNCALIBRATED MODE" in texts(at)
    labels = [m.label for m in at.metric]
    assert "Apparent width (px)" in labels and "Bead width (mm)" not in labels
    assert {d.label for d in at.get("download_button")} >= {L.DOWNLOAD_JSON, L.DOWNLOAD_CSV}


def test_calibrated_app_shows_mm(monkeypatch, tmp_path, synth_cal):
    cfg = copy.deepcopy(synth_cal["cfg"])
    cal = save_calibration(copy.deepcopy(synth_cal["calibration_data"]), tmp_path / "cal.json")
    cfg["calibration"]["enabled"] = True
    cfg["calibration"]["calibration_file"] = str(cal)
    p = save_config(cfg, tmp_path / "config.yaml")
    img, _ = render_weld_image(demo_rig(), BeadSpec(8, 2, 5, 160), seed=1)
    at = run_app(monkeypatch, p, img)
    assert not at.exception
    assert "CALIBRATED MODE (mm)" in texts(at)
    metrics = {m.label: m.value for m in at.metric}
    assert "Bead width (mm)" in metrics
    assert float(metrics["Bead height (mm)"]) == pytest.approx(2.0, rel=0.05)


def test_calibrated_app_blocked_with_invalid_calibration(monkeypatch, tmp_path):
    cfg = safe_defaults()
    cfg["calibration"]["enabled"] = True
    cfg["calibration"]["calibration_file"] = str(tmp_path / "missing.json")
    p = save_config(cfg, tmp_path / "config.yaml")
    img, _ = render_weld_image(demo_rig(), BeadSpec(8, 2, 5, 160), seed=1)
    at = run_app(monkeypatch, p, img)
    assert not at.exception
    t = texts(at)
    assert "BLOCKED" in t and "Processing is blocked" in t
    assert not [m for m in at.metric if "(mm)" in m.label]


def test_invalid_yaml_shows_error(monkeypatch, tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("calibration:\n  enabled: maybe\n")
    at = run_app(monkeypatch, p)
    assert not at.exception
    assert "config/config.yaml has problems" in texts(at)


def test_all_calibration_steps_render(monkeypatch, tmp_path):
    p = save_config(safe_defaults(), tmp_path / "config.yaml")
    at = run_app(monkeypatch, p)
    for step in (L.STEP_BOARD, L.STEP_INTRINSICS, L.STEP_LASER, L.STEP_VALIDATION, L.STEP_STATUS):
        radio = next(r for r in at.radio if r.label == L.CAL_STEP)
        at = radio.set_value(step).run()
        assert not at.exception, step
    radio = next(r for r in at.radio if r.label == L.CAL_STEP)
    at = radio.set_value(L.STEP_BOARD).run()
    next(b for b in at.button if b.label == L.GENERATE_PDF).click().run()
    assert {L.DOWNLOAD_PDF, L.DOWNLOAD_SVG} <= {d.label for d in at.get("download_button")}
