"""JSON / CSV export of measurement results."""
from __future__ import annotations

import csv
import io
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np


CSV_COLUMNS = ["index", "image_u_px", "image_v_px", "valid", "point_confidence", "along_line_px", "stripe_center_px",
               "height_above_reference_px", "X_mm", "Y_mm", "Z_mm", "profile_s_mm", "profile_h_mm", "height_above_reference_mm",
               "metric_validated", "triangulation_status"]


def _clean(obj: Any) -> Any:
    """Make numpy / NaN JSON-safe (NaN and inf become null)."""
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return _clean(obj.tolist())
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return f if math.isfinite(f) else None
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def result_to_json(result) -> str:
    return json.dumps(_clean(result.to_dict()), indent=2)


def result_to_csv(result) -> str:
    prof = result.profile
    uv = prof.image_uv()
    hcurve = result.pixel.height_curve or [float("nan")] * len(prof.x)
    validated = bool(result.metric and result.metric.get("validated"))
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_COLUMNS)
    pts = result.metric_points
    reasons = result.metric_reasons

    def fmt(v):
        return "" if v is None or (isinstance(v, float) and not math.isfinite(v)) else f"{v:.6g}"

    for i in range(len(prof.x)):
        u, v = uv[i]
        valid = bool(np.isfinite(prof.y[i]))
        row = [i, fmt(float(u)), fmt(float(v)), int(valid), fmt(float(prof.confidence[i])), fmt(float(prof.x[i])),
               fmt(float(prof.y[i])), fmt(float(hcurve[i]) if i < len(hcurve) else None)]
        if pts is not None and validated:
            X, Y, Z = pts[i]
            hc = result.metric_height_curve
            row += [fmt(float(X)), fmt(float(Y)), fmt(float(Z)), fmt(float(result.metric_s[i])),
                    fmt(float(result.metric_h[i])), fmt(float(hc[i])) if hc is not None else "", 1,
                    "" if reasons is None else str(reasons[i])]
        else:
            row += ["", "", "", "", "", "", 0, ""]
        writer.writerow(row)
    return buf.getvalue()


def save_result_files(result, out_dir: Path, images: dict[str, np.ndarray] | None, cfg: dict[str, Any]) -> list[Path]:
    from utils.image_io import save_image
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = out_dir / f"measurement_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    if cfg["output"]["save_json"]:
        p = folder / "result.json"
        p.write_text(result_to_json(result), encoding="utf-8")
        written.append(p)
    if cfg["output"]["save_profiles"]:
        p = folder / "profile.csv"
        p.write_text(result_to_csv(result), encoding="utf-8")
        written.append(p)
    if cfg["output"]["save_debug_images"] and images:
        for name, img in images.items():
            written.append(save_image(img, folder / f"{name}.png"))
    return written
