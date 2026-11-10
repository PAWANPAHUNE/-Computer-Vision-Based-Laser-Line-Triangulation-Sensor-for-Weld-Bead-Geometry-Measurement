"""Image decoding/encoding and overlay drawing helpers."""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def decode_image(data: bytes) -> np.ndarray:
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("This file is not a readable image (use JPG, PNG or BMP).")
    return img


def encode_png(image: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", image)
    if not ok:
        raise ValueError("Could not encode image.")
    return buf.tobytes()


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if image.ndim == 3 else image


def save_image(image: np.ndarray, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not write {path}")
    return path


def draw_stripe_overlay(image_bgr: np.ndarray, uv_all: np.ndarray, boundaries_uv: list[np.ndarray] | None = None,
                        peak_uv: np.ndarray | None = None) -> np.ndarray:
    """Green centreline, yellow bead boundaries, cyan peak."""
    out = image_bgr.copy()
    ok = np.all(np.isfinite(uv_all), axis=1)
    pts = uv_all.copy()
    # Draw continuous pieces only.
    seg_start = None
    for i in range(len(pts) + 1):
        good = i < len(pts) and ok[i]
        if good and seg_start is None:
            seg_start = i
        if not good and seg_start is not None:
            piece = np.round(pts[seg_start:i] * 4).astype(np.int32)
            if len(piece) >= 2:
                cv2.polylines(out, [piece], False, (0, 255, 0), 2, cv2.LINE_AA, shift=2)
            seg_start = None
    for b in boundaries_uv or []:
        if b is not None and np.all(np.isfinite(b)):
            cv2.circle(out, (int(round(b[0])), int(round(b[1]))), 7, (0, 255, 255), 2, cv2.LINE_AA)
    if peak_uv is not None and np.all(np.isfinite(peak_uv)):
        cv2.drawMarker(out, (int(round(peak_uv[0])), int(round(peak_uv[1]))), (255, 255, 0), cv2.MARKER_CROSS, 18, 2)
    return out


def mask_to_bgr(mask: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
