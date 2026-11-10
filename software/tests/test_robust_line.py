"""Laser-pose straightness test: a few stray edge points are ignored, a bent board is still rejected."""
from __future__ import annotations

import numpy as np

from calibration.triangulation import robust_line_3d


def _line(n=100, noise=0.2, seed=0):
    rng = np.random.default_rng(seed)
    t = np.linspace(-80, 80, n)
    pts = np.stack([t, 0.3 * t, 590 + 0.1 * t], 1)
    return pts + rng.normal(0, noise, pts.shape)


def test_few_stray_points_ignored():
    pts = _line()
    pts[:3] += [0, 0, 40.0]        # laser ran off the board edge onto the floor
    pts[-1] += [0, 89.0, 0]        # one far-away reflection
    _, _, rms, keep = robust_line_3d(pts, 1.5)
    assert keep.sum() == 96 and not keep[:3].any() and not keep[-1]
    assert rms < 0.4


def test_bent_board_keeps_few_inliers():
    t = np.linspace(-80, 80, 100)
    bent = np.stack([t, np.zeros_like(t), 590 + 0.004 * t ** 2], 1)   # 25 mm sag over 160 mm
    _, _, _, keep = robust_line_3d(bent, 1.5)
    assert keep.mean() < 0.75


def test_single_spike_is_not_an_object():
    from vision.weld_measurement import MeasurementSettings, measure_profile
    x = np.linspace(0, 200, 200)
    y = np.random.default_rng(1).normal(0, 0.3, x.size)
    y[120] = 56.0                                  # one stray red dot far above the floor line
    m = measure_profile(x, y, MeasurementSettings(units="mm", min_bead_height=0.2, boundary_fraction=0.5,
                                                  bead_direction="positive"))
    assert m.status == "no_bead" and any("stray red dot" in w for w in m.warnings)
