"""Weld width/height extraction and the mode rules for reported units."""
from __future__ import annotations

import copy

import numpy as np
import pytest

from calibration.validation import resolve_mode
from synthetic.demo import calibrated_mode_for, demo_rig
from synthetic.scene import BeadSpec, SyntheticRig, render_weld_image
from vision.pipeline import ReferenceScale, run_measurement
from vision.weld_measurement import MeasurementSettings, measure_profile

S_PX = MeasurementSettings(units="px", min_bead_height=3.0)


def cap_profile(n=600, centre=300.0, width=120.0, height=20.0, slope=0.0, offset=50.0, noise=0.0, sign=1, seed=0):
    x = np.arange(n, dtype=float)
    u = 2 * (x - centre) / width
    bump = np.where(np.abs(u) < 1, height * np.sqrt(np.clip(1 - u ** 2, 0, None)), 0.0)
    y = offset + slope * x + sign * bump * np.sqrt(1 + slope ** 2)
    y += np.random.default_rng(seed).normal(0, noise, n) if noise else 0
    return x, y


def test_known_width_and_height():
    x, y = cap_profile()
    m = measure_profile(x, y, S_PX)
    assert m.status == "ok"
    assert m.width == pytest.approx(120.0, rel=0.02)
    assert m.height == pytest.approx(20.0, rel=0.01)
    assert m.peak_x == pytest.approx(300.0, abs=1.0)
    assert m.confidence > 0.9


def test_bead_not_centred():
    x, y = cap_profile(centre=110.0, width=80.0)
    m = measure_profile(x, y, S_PX)
    assert m.status == "ok" and m.peak_x == pytest.approx(110.0, abs=1.0)
    assert m.width == pytest.approx(80.0, rel=0.03)


def test_tilted_reference_surface():
    x, y = cap_profile(slope=0.2)
    m = measure_profile(x, y, S_PX)
    assert m.base_slope == pytest.approx(0.2, abs=1e-3)
    # width measured along the tilted base line
    assert m.width == pytest.approx(120.0 * np.sqrt(1 + 0.04), rel=0.03)
    assert m.height == pytest.approx(20.0, rel=0.02)


def test_negative_direction_auto_and_forced():
    x, y = cap_profile(sign=-1)
    m = measure_profile(x, y, S_PX)
    assert m.bead_sign == -1 and m.height == pytest.approx(20.0, rel=0.01)
    forced = measure_profile(x, y, MeasurementSettings(units="px", min_bead_height=3.0, bead_direction="positive"))
    assert forced.status == "no_bead"


def test_noise_and_missing_points():
    x, y = cap_profile(noise=0.5, seed=2)
    y[200:215] = np.nan
    y[330:340] = np.nan
    m = measure_profile(x, y, S_PX)
    assert m.status == "ok"
    assert m.height == pytest.approx(20.0, abs=1.5)
    assert m.width == pytest.approx(120.0, rel=0.05)


def test_flat_profile_has_no_bead():
    x = np.arange(300.0)
    m = measure_profile(x, 100 + 0.01 * x, S_PX)
    assert m.status == "no_bead"


def test_insufficient_data():
    m = measure_profile(np.arange(5.0), np.ones(5), S_PX)
    assert m.status == "insufficient_data"


def test_bead_at_edge_warns():
    x, y = cap_profile(centre=20.0, width=120.0)
    m = measure_profile(x, y, S_PX)
    assert any("lower bound" in w or "left side" in w for w in m.warnings)
    assert m.confidence < 0.9


def test_global_line_reference_mode():
    x, y = cap_profile()
    m = measure_profile(x, y, MeasurementSettings(units="px", min_bead_height=3.0, reference_surface="global_line"))
    assert m.height == pytest.approx(20.0, rel=0.01)


# --------------------------------------------------------------- pipeline + modes
def synthetic_weld(rig=None, bead=None, **kw):
    return render_weld_image(rig or SyntheticRig(), bead or BeadSpec(8.0, 2.0, 5.0, 150.0), seed=5, **kw)


def test_uncalibrated_reports_pixels_only(cfg):
    img, truth = synthetic_weld()
    res = run_measurement(img, cfg, resolve_mode(cfg))
    d = res.to_dict()
    assert res.metric is None and d["metric_measurement"] is None
    assert d["pixel_measurement"]["units"] == "px"
    assert "NOT millimetres" in d["pixel_measurement"]["meaning"]
    assert res.experimental_estimates == []           # disabled by default
    assert res.pixel.height == pytest.approx(truth["height_px"], rel=0.05)
    assert res.pixel.width == pytest.approx(truth["width_px"], rel=0.08)


def test_reference_scale_needs_explicit_permission(cfg):
    img, _ = synthetic_weld()
    ref = ReferenceScale(0.1, 0.3, "test")
    assert run_measurement(img, cfg, resolve_mode(cfg), reference=ref).experimental_estimates == []
    cfg["calibration"]["allow_uncalibrated_metric_estimates"] = True
    res = run_measurement(img, cfg, resolve_mode(cfg), reference=ref)
    est = res.experimental_estimates[0]
    assert est["label"].startswith("EXPERIMENTAL")
    assert est["width_mm"] == pytest.approx(res.pixel.width * 0.1)
    assert res.metric is None  # still no validated mm


def test_nominal_estimate_matches_truth_when_geometry_exact(cfg):
    rig = SyntheticRig()
    img, _ = synthetic_weld(rig)
    cfg["calibration"]["allow_uncalibrated_metric_estimates"] = True
    g = rig.config_geometry()
    cfg["camera"].update(g["camera"])
    cfg["geometry"].update(g["geometry"])
    for k in ("camera.focal_length_mm", "camera.pixel_pitch_um", "geometry.camera_to_laser_baseline_mm",
              "geometry.camera_pitch_deg", "geometry.laser_plane_angle_deg"):
        cfg["parameter_sources"][k] = {"source": "measured", "note": "synthetic"}
    res = run_measurement(img, cfg, resolve_mode(cfg))
    est = next(e for e in res.experimental_estimates if e.get("available"))
    assert "EXPERIMENTAL" in est["label"]
    assert est["height_mm"] == pytest.approx(2.0, rel=0.05)
    assert est["width_mm"] == pytest.approx(8.0, rel=0.08)


def test_nominal_estimate_unavailable_lists_missing(cfg):
    cfg["calibration"]["allow_uncalibrated_metric_estimates"] = True
    img, _ = synthetic_weld()
    res = run_measurement(img, cfg, resolve_mode(cfg))
    est = res.experimental_estimates[-1]
    assert est["available"] is False and "focal_length_mm" in est["reason"]


def test_calibrated_metric_measurement(synth_cal):
    cfg = copy.deepcopy(synth_cal["cfg"])
    cfg["calibration"]["enabled"] = True
    mode = calibrated_mode_for(synth_cal["calibration_data"], cfg)
    assert mode.metric_allowed, mode.messages
    for bead in (BeadSpec(8.0, 2.0, 5.0, 160.0), BeadSpec(10.0, 3.0, -5.0, 175.0)):
        img, _ = render_weld_image(demo_rig(), bead, seed=9)
        res = run_measurement(img, cfg, mode)
        assert res.metric["validated"] is True
        assert res.metric["units"] == "mm"
        assert res.metric["height"] == pytest.approx(bead.height_mm, rel=0.05)
        assert res.metric["width"] == pytest.approx(bead.width_mm, rel=0.10)


def test_calibrated_withholds_low_confidence(synth_cal):
    cfg = copy.deepcopy(synth_cal["cfg"])
    cfg["calibration"]["enabled"] = True
    cfg["measurement"]["minimum_confidence"] = 0.99
    mode = calibrated_mode_for(synth_cal["calibration_data"], cfg)
    img, _ = render_weld_image(demo_rig(), BeadSpec(8.0, 2.0, 5.0, 160.0), seed=9, intensity=45.0, noise=8.0)
    res = run_measurement(img, cfg, mode)
    assert res.metric["validated"] is False
    assert res.blocked_reason and "withheld" in res.blocked_reason


def test_calibrated_resolution_mismatch_blocks_metric(synth_cal):
    import cv2
    cfg = copy.deepcopy(synth_cal["cfg"])
    cfg["calibration"]["enabled"] = True
    mode = calibrated_mode_for(synth_cal["calibration_data"], cfg)
    img, _ = render_weld_image(demo_rig(), BeadSpec(8.0, 2.0, 5.0, 160.0), seed=9)
    small = cv2.resize(img, (640, 400))
    res = run_measurement(small, cfg, mode)
    assert res.metric is None and "640x400" in res.blocked_reason
    cfg["calibration"]["allow_intrinsic_resolution_scaling"] = True
    res2 = run_measurement(small, cfg, mode)
    assert res2.metric is not None  # scaling explicitly allowed


def test_blocked_mode_refuses_processing(tmp_path, cfg):
    cfg["calibration"]["enabled"] = True
    cfg["calibration"]["calibration_file"] = str(tmp_path / "none.json")
    img, _ = synthetic_weld()
    with pytest.raises(PermissionError):
        run_measurement(img, cfg, resolve_mode(cfg))
