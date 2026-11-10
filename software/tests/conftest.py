"""Shared fixtures. All data here is synthetic."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from calibration.calibration_file import save_calibration
from synthetic.demo import synthetic_calibration
from utils.config_loader import safe_defaults

PROJECT = Path(__file__).resolve().parent.parent


@pytest.fixture
def cfg():
    return safe_defaults()


@pytest.fixture(scope="session")
def synth_cal():
    """Full synthetic camera + laser calibration (computed once per test session)."""
    out = synthetic_calibration()
    assert out["intrinsics"].ok, out["intrinsics"].errors
    assert out["laser"].ok, out["laser"].errors
    return out


@pytest.fixture
def calibrated_setup(tmp_path, synth_cal):
    """A config dict in calibrated mode + a valid calibration file in tmp_path."""
    cfg = copy.deepcopy(synth_cal["cfg"])
    path = tmp_path / "calibration.json"
    save_calibration(copy.deepcopy(synth_cal["calibration_data"]), path)
    cfg["calibration"]["enabled"] = True
    cfg["calibration"]["calibration_file"] = str(path)
    return cfg, path


def write_yaml(path: Path, data: dict) -> Path:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path


def edit_json(path: Path, fn) -> None:
    data = json.loads(path.read_text())
    fn(data)
    path.write_text(json.dumps(data))


def straight_stripe_image(h=400, w=600, center=200.3, sigma=1.5, amplitude=180.0, horizontal=True, noise=0.0,
                          seed=0, background=60.0):
    """Analytic Gaussian stripe at a known sub-pixel position."""
    rng = np.random.default_rng(seed)
    if horizontal:
        rows = np.arange(h)[:, None]
        prof = np.exp(-0.5 * ((rows - center) / sigma) ** 2) * np.ones((1, w))
    else:
        cols = np.arange(w)[None, :]
        prof = np.exp(-0.5 * ((cols - center) / sigma) ** 2) * np.ones((h, 1))
    img = np.full((h, w, 3), background, np.float64)
    img[..., 2] += amplitude * prof
    img[..., 1] += 0.1 * amplitude * prof
    img += rng.normal(0, noise, img.shape) if noise else 0
    return np.clip(img, 0, 255).astype(np.uint8)
