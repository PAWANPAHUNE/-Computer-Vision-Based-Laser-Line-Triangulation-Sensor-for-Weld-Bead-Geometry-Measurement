"""JSON and CSV exports."""
from __future__ import annotations

import copy
import csv
import io
import json

from calibration.validation import resolve_mode
from synthetic.demo import calibrated_mode_for, demo_rig
from synthetic.scene import BeadSpec, SyntheticRig, render_weld_image
from utils.export import CSV_COLUMNS, result_to_csv, result_to_json, save_result_files
from vision.pipeline import run_measurement


def test_uncalibrated_exports(cfg, tmp_path):
    img, _ = render_weld_image(SyntheticRig(), BeadSpec(8, 2, 5, 150), seed=1, gaps_mm=[(-30, -25)])
    res = run_measurement(img, cfg, resolve_mode(cfg))
    data = json.loads(result_to_json(res))  # strict JSON: NaN would fail json.loads? -> check text too
    assert "NaN" not in result_to_json(res)
    assert data["mode"] == "uncalibrated" and data["metric_measurement"] is None
    assert data["pixel_measurement"]["width"] == res.pixel.width
    rows = list(csv.reader(io.StringIO(result_to_csv(res))))
    assert rows[0] == CSV_COLUMNS
    assert len(rows) - 1 == len(res.profile.x)
    body = rows[1:]
    assert all(r[CSV_COLUMNS.index("X_mm")] == "" for r in body)           # no mm in uncalibrated mode
    assert all(r[CSV_COLUMNS.index("metric_validated")] == "0" for r in body)
    assert any(r[CSV_COLUMNS.index("valid")] == "0" for r in body)          # gap rows kept, marked invalid
    files = save_result_files(res, tmp_path, {"original": img}, cfg)
    assert {f.name for f in files} == {"result.json", "profile.csv", "original.png"}


def test_calibrated_exports_contain_mm(synth_cal):
    cfg = copy.deepcopy(synth_cal["cfg"])
    cfg["calibration"]["enabled"] = True
    mode = calibrated_mode_for(synth_cal["calibration_data"], cfg)
    img, _ = render_weld_image(demo_rig(), BeadSpec(8, 2, 5, 160), seed=2)
    res = run_measurement(img, cfg, mode)
    data = json.loads(result_to_json(res))
    assert data["metric_measurement"]["units"] == "mm" and data["metric_measurement"]["validated"] is True
    assert data["calibration_fingerprint"] == synth_cal["calibration_data"]["integrity_sha256"]
    rows = list(csv.DictReader(io.StringIO(result_to_csv(res))))
    valid = [r for r in rows if r["valid"] == "1"]
    assert valid and all(r["Z_mm"] != "" and r["metric_validated"] == "1" for r in valid[:50])
    assert 100 < float(valid[0]["Z_mm"]) < 300
