"""Laser stripe detection on synthetic images: brightness, noise, gaps, curves, reflections."""
from __future__ import annotations

import numpy as np
import pytest

from synthetic.scene import splat_curve
from tests.conftest import straight_stripe_image
from vision.laser_detection import (AXIS_COLUMNS, AXIS_ROWS, LaserDetectionParams, choose_axis, compute_red_score,
                                    detect_laser_stripe, nan_median_filter, reject_outliers)

P = LaserDetectionParams()


def curve_image(fn, h=480, w=640, amplitude=170.0, noise=0.0, sigma=1.5, seed=0, gaps=()):
    x = np.arange(0, w, 0.05)
    y = fn(x)
    uv = np.column_stack([x, y])
    for a, b in gaps:
        uv[(x >= a) & (x <= b)] = np.nan
    ridge = splat_curve(uv, (h, w), sigma)
    ridge /= ridge.max()
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 70.0)
    img[..., 2] += amplitude * ridge
    img[..., 1] += 0.1 * amplitude * ridge
    img += rng.normal(0, noise, img.shape)
    return np.clip(img, 0, 255).astype(np.uint8), x, y


@pytest.mark.parametrize("amplitude", [50.0, 120.0, 190.0])
def test_subpixel_horizontal_stripe(amplitude):
    img = straight_stripe_image(center=200.3, amplitude=amplitude)
    st = detect_laser_stripe(img, P, axis="auto")
    assert st.axis == AXIS_COLUMNS
    assert st.coverage > 0.99
    assert np.nanmax(np.abs(st.centers - 200.3)) < 0.1


def test_vertical_stripe_uses_rows():
    img = straight_stripe_image(center=311.7, horizontal=False)
    st = detect_laser_stripe(img, P, axis="auto")
    assert st.axis == AXIS_ROWS
    assert np.nanmax(np.abs(st.centers - 311.7)) < 0.1
    uv = st.image_points()
    assert np.allclose(uv[:, 0], st.centers[st.valid])  # u = column for a vertical stripe


def test_noise_robustness():
    img = straight_stripe_image(center=150.6, amplitude=150, noise=10.0, seed=3)
    st = detect_laser_stripe(img, P)
    assert st.coverage > 0.95
    assert np.nanmedian(np.abs(st.centers - 150.6)) < 0.2


def test_curved_profile_followed():
    fn = lambda x: 240 + 30 * np.sin(x / 60.0)  # noqa: E731
    img, x, y = curve_image(fn, noise=3)
    st = detect_laser_stripe(img, P, axis=AXIS_COLUMNS)
    cols = np.arange(img.shape[1])
    truth = fn(cols)
    ok = st.valid
    assert ok.mean() > 0.95
    assert np.median(np.abs(st.centers[ok] - truth[ok])) < 0.15


def test_step_profile_preserved():
    fn = lambda x: np.where((x > 250) & (x < 350), 220.0, 240.0)  # noqa: E731  20 px bead plateau
    img, _, _ = curve_image(fn)
    st = detect_laser_stripe(img, P, axis=AXIS_COLUMNS)
    assert np.nanmin(st.centers[260:340]) == pytest.approx(220.0, abs=0.3)  # peak not flattened
    assert np.nanmedian(st.centers[:200]) == pytest.approx(240.0, abs=0.2)


def test_gaps_and_fragments():
    fn = lambda x: 200 + 0 * x  # noqa: E731
    img, _, _ = curve_image(fn, gaps=[(100, 160), (400, 430)])
    st = detect_laser_stripe(img, P, axis=AXIS_COLUMNS)
    assert not st.valid[110:150].any()
    assert st.valid[200:380].all()
    assert st.n_segments >= 3


def test_missing_stripe_warns():
    img = np.full((300, 400, 3), 80, np.uint8)
    st = detect_laser_stripe(img, P)
    assert not st.valid.any()
    assert st.overall_confidence == 0.0
    assert any("No laser stripe" in w for w in st.warnings)


def test_weak_stripe_low_confidence_or_missing():
    img = straight_stripe_image(amplitude=25.0, noise=6.0)
    st = detect_laser_stripe(img, P)
    assert st.overall_confidence < 0.6


def test_reflection_blob_not_followed():
    img = straight_stripe_image(h=400, w=600, center=300.0)
    img = img.astype(np.float64)
    img[150:175, 250:300, 2] += 200  # bright red blob far above the stripe, wider than the stripe
    img = np.clip(img, 0, 255).astype(np.uint8)
    st = detect_laser_stripe(img, P, axis=AXIS_COLUMNS)
    assert np.nanmax(np.abs(st.centers[250:300] - 300.0)) < 0.5
    assert st.multi_run_fraction > 0


def test_saturated_white_core_recovered():
    img = straight_stripe_image(center=200.0, amplitude=180)
    img[199:202, :, :] = 255  # white core
    st = detect_laser_stripe(img, P)
    assert st.coverage > 0.99
    assert np.nanmax(np.abs(st.centers - 200.0)) < 0.3


def test_roi_mask_limits_detection():
    img = straight_stripe_image(center=200.0)
    roi = np.zeros(img.shape[:2], np.uint8)
    roi[:, :300] = 255
    st = detect_laser_stripe(img, P, axis=AXIS_COLUMNS, roi_mask=roi)
    assert st.valid[:290].all() and not st.valid[310:].any()


def test_glare_wider_than_limit_rejected():
    img = np.full((300, 400, 3), 60, np.uint8)
    img[100:180, :, 2] = 250  # 80 px tall red band
    st = detect_laser_stripe(img, LaserDetectionParams(max_stripe_width_px=40))
    assert not st.valid.any()


def test_methods_all_find_a_clear_stripe():
    img = straight_stripe_image(center=123.4, amplitude=160)
    for method in ("red_channel_difference", "hsv_red", "red_channel_tophat"):
        st = detect_laser_stripe(img, LaserDetectionParams(detection_method=method), axis=AXIS_COLUMNS)
        assert st.coverage > 0.95, method
        assert np.nanmedian(np.abs(st.centers - 123.4)) < 0.3, method


def test_unknown_method_raises():
    with pytest.raises(ValueError):
        compute_red_score(np.zeros((10, 10, 3), np.uint8), LaserDetectionParams(detection_method="x"))


def test_choose_axis():
    m = np.zeros((100, 200), np.uint8)
    m[50, 10:190] = 255
    assert choose_axis(m) == AXIS_COLUMNS
    assert choose_axis(m.T.copy()) == AXIS_ROWS


def test_outlier_rejection_keeps_steps():
    c = np.full(60, 100.0)
    c[30:] = 120.0       # real step
    c[10] = 150.0        # spike
    out, n = reject_outliers(c, 6.0, 7)
    assert np.isnan(out[10]) and n == 1
    assert np.all(np.isfinite(out[25:35]))


def test_median_filter_respects_gaps():
    v = np.array([1, 1, 1, np.nan, 5, 5, 5, 5], float)
    out = nan_median_filter(v, 3)
    assert np.isnan(out[3]) and np.allclose(out[:3], 1) and np.allclose(out[4:], 5)
