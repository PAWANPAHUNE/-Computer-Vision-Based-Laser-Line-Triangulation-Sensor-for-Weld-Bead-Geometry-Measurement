"""Red laser stripe detection with sub-pixel centre extraction.

Pipeline (one image):

1. Red score image (0-255, float). Methods:
   * ``red_channel_difference``: R - max(G, B). A laser core that saturates to
     white (R=G=B=255) is restored when it sits next to red halo pixels.
   * ``hsv_red``: brightness of pixels whose hue is red and saturation high.
   * ``red_channel_tophat``: R minus its local background (morphological top-hat),
     useful when the scene is uniformly reddish.
2. Threshold, then remove connected components smaller than ``minimum_component_area``.
3. Choose the scan axis. For each scan line (image column for a mostly horizontal
   stripe, image row for a mostly vertical stripe) find the runs of mask pixels,
   keep the run with the largest summed score, and compute its
   intensity-weighted centroid (sub-pixel). Runs wider than ``max_stripe_width_px``
   are glare and rejected.
   Where a line has several red runs (reflections), the run that continues the stripe from the
   nearest unambiguous lines is chosen, not simply the brightest.
4. Outliers: a centre that differs by more than ``outlier_threshold_px`` from BOTH
   the median of its left neighbours and of its right neighbours is removed. A real
   step (bead toe) agrees with one side, so it is kept.
5. Smoothing: a NaN-aware median filter applied inside each continuous segment.
   A median keeps sharp peaks and steps better than a moving average.

Detection never touches geometry; it only returns image coordinates.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

AXIS_COLUMNS = "image_columns"   # one centre per image column (stripe runs left-right)
AXIS_ROWS = "image_rows"         # one centre per image row (stripe runs top-bottom)
MIN_ALBEDO = 0.5                 # with a laser-OFF image: ignore dark (black-square) pixels


@dataclass
class LaserDetectionParams:
    detection_method: str = "red_channel_difference"
    threshold: float = 30.0
    minimum_component_area: int = 5
    smoothing_window: int = 5
    blur_kernel: int = 3
    max_stripe_width_px: float = 40.0
    outlier_threshold_px: float = 6.0
    saturation_level: int = 250
    min_segment_length: int = 3
    neighbour_window: int = 7

    @classmethod
    def from_config(cls, laser_cfg: dict[str, Any]) -> "LaserDetectionParams":
        keys = {"detection_method", "threshold", "minimum_component_area", "smoothing_window", "blur_kernel",
                "max_stripe_width_px", "outlier_threshold_px", "saturation_level"}
        return cls(**{k: laser_cfg[k] for k in keys if k in laser_cfg})


@dataclass
class StripeResult:
    """Stripe centres in image coordinates.

    ``positions[i]`` is the scan-line index (column for AXIS_COLUMNS, row for AXIS_ROWS);
    ``centers[i]`` is the sub-pixel position across the scan line, NaN where no valid stripe.
    """
    axis: str
    positions: np.ndarray
    centers: np.ndarray
    raw_centers: np.ndarray
    confidence: np.ndarray
    widths: np.ndarray
    score: np.ndarray
    mask: np.ndarray
    image_shape: tuple[int, int]
    warnings: list[str] = field(default_factory=list)
    multi_run_fraction: float = 0.0
    saturated_fraction: float = 0.0
    outliers_removed: int = 0

    @property
    def valid(self) -> np.ndarray:
        return np.isfinite(self.centers)

    @property
    def coverage(self) -> float:
        return float(self.valid.mean()) if self.centers.size else 0.0

    @property
    def n_segments(self) -> int:
        return len(_segments(self.valid))

    @property
    def overall_confidence(self) -> float:
        v = self.valid
        if not v.any():
            return 0.0
        return float(np.clip(self.coverage * np.mean(self.confidence[v]), 0.0, 1.0)) ** 0.5

    def image_points(self) -> np.ndarray:
        """(N, 2) array of (u, v) pixel coordinates for valid centres, in scan order."""
        v = self.valid
        if self.axis == AXIS_COLUMNS:
            return np.column_stack([self.positions[v].astype(np.float64), self.centers[v]])
        return np.column_stack([self.centers[v], self.positions[v].astype(np.float64)])

    def summary(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "coverage": round(self.coverage, 4),
            "valid_points": int(self.valid.sum()),
            "segments": self.n_segments,
            "mean_point_confidence": round(float(np.mean(self.confidence[self.valid])), 4) if self.valid.any() else 0.0,
            "detection_confidence": round(self.overall_confidence, 4),
            "multi_run_fraction": round(self.multi_run_fraction, 4),
            "saturated_fraction": round(self.saturated_fraction, 4),
            "outliers_removed": self.outliers_removed,
            "warnings": list(self.warnings),
        }


# ------------------------------------------------------------------ scores
def laser_only_image(laser_on_bgr: np.ndarray, laser_off_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Laser light alone (ON - OFF) and the scene albedo (0.15..1) from the OFF image.

    Used when a laser-OFF picture of the same, unmoved scene exists (calibration poses). The static
    pattern cancels, the score is divided by the albedo, and pixels darker than ``MIN_ALBEDO``
    (black squares) are excluded: scan lines whose centroid window touches them are skipped, so
    black/white edges cannot pull the stripe centre.
    """
    if laser_on_bgr.shape != laser_off_bgr.shape:
        raise ValueError("Laser ON and OFF images must have the same size.")
    diff = np.clip(laser_on_bgr.astype(np.int16) - laser_off_bgr.astype(np.int16), 0, 255).astype(np.uint8)
    gray = cv2.cvtColor(laser_off_bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    ref = float(np.percentile(gray, 95)) or 1.0
    albedo = np.clip(gray / ref, 0.05, 1.0)
    return diff, albedo


def compute_red_score(image_bgr: np.ndarray, params: LaserDetectionParams) -> tuple[np.ndarray, np.ndarray]:
    """Return (score float32 0..255, saturated-core mask bool)."""
    if image_bgr is None or image_bgr.ndim != 3 or image_bgr.shape[2] != 3:
        raise ValueError("Expected a colour (BGR) image with 3 channels.")
    img = image_bgr
    if params.blur_kernel and params.blur_kernel > 1:
        img = cv2.GaussianBlur(img, (int(params.blur_kernel), int(params.blur_kernel)), 0)
    b, g, r = [c.astype(np.float32) for c in cv2.split(img)]
    saturated = np.zeros(r.shape, dtype=bool)
    method = params.detection_method
    if method == "red_channel_difference":
        score = np.clip(r - np.maximum(g, b), 0, 255)
        # White, saturated laser core: R saturated and adjacent to red-dominant halo.
        sat = r >= params.saturation_level
        if sat.any():
            halo = (score >= params.threshold).astype(np.uint8)
            near_halo = cv2.dilate(halo, np.ones((7, 7), np.uint8)) > 0
            saturated = sat & near_halo & (score < params.threshold)
            score = np.where(saturated, 255.0, score)
    elif method == "hsv_red":
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h, s, v = hsv[..., 0].astype(np.int32), hsv[..., 1].astype(np.float32), hsv[..., 2].astype(np.float32)
        red_hue = (h <= 10) | (h >= 170)
        score = np.where(red_hue & (s >= 80), v, 0.0).astype(np.float32)
    elif method == "red_channel_tophat":
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (31, 31))
        score = cv2.morphologyEx(r, cv2.MORPH_TOPHAT, kernel)
    else:
        raise ValueError(f"Unknown laser detection method {method!r}.")
    return score.astype(np.float32), saturated


def threshold_mask(score: np.ndarray, params: LaserDetectionParams, roi_mask: np.ndarray | None = None) -> np.ndarray:
    mask = (score >= params.threshold).astype(np.uint8)
    if roi_mask is not None:
        mask &= (roi_mask > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros(n, dtype=bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= params.minimum_component_area
    return keep[labels].astype(np.uint8) * 255


def choose_axis(mask: np.ndarray) -> str:
    """Mostly-horizontal stripe -> scan columns; mostly-vertical -> scan rows (PCA of mask pixels)."""
    ys, xs = np.nonzero(mask)
    if xs.size < 10:
        return AXIS_COLUMNS
    cov = np.cov(np.vstack([xs, ys]).astype(np.float64))
    evals, evecs = np.linalg.eigh(cov)
    major = evecs[:, int(np.argmax(evals))]
    return AXIS_COLUMNS if abs(major[0]) >= abs(major[1]) else AXIS_ROWS


# --------------------------------------------------------------- helpers
def _segments(valid: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive-exclusive (start, stop) index ranges of consecutive True values."""
    if valid.size == 0:
        return []
    padded = np.concatenate([[False], valid.astype(bool), [False]])
    diff = np.diff(padded.astype(np.int8))
    starts = np.nonzero(diff == 1)[0]
    stops = np.nonzero(diff == -1)[0]
    return list(zip(starts.tolist(), stops.tolist()))


def nan_median_filter(values: np.ndarray, window: int) -> np.ndarray:
    """Median filter applied separately inside each continuous non-NaN segment."""
    out = values.astype(np.float64).copy()
    if window <= 1:
        return out
    half = window // 2
    for start, stop in _segments(np.isfinite(values)):
        seg = values[start:stop].astype(np.float64)
        if seg.size < 3:
            continue
        padded = np.pad(seg, half, mode="edge")
        windows = np.lib.stride_tricks.sliding_window_view(padded, window)
        out[start:stop] = np.median(windows, axis=1)
    return out


def reject_outliers(centers: np.ndarray, threshold: float, window: int) -> tuple[np.ndarray, int]:
    """Remove points that disagree with BOTH their left and right neighbourhoods."""
    c = centers.astype(np.float64).copy()
    idx = np.nonzero(np.isfinite(c))[0]
    if idx.size < 5:
        return c, 0
    vals = c[idx]
    removed = 0
    bad = np.zeros(idx.size, dtype=bool)
    for k in range(idx.size):
        left = vals[max(0, k - window):k]
        right = vals[k + 1:k + 1 + window]
        dl = abs(vals[k] - np.median(left)) if left.size >= 2 else None
        dr = abs(vals[k] - np.median(right)) if right.size >= 2 else None
        checks = [d for d in (dl, dr) if d is not None]
        if checks and all(d > threshold for d in checks):
            bad[k] = True
    removed = int(bad.sum())
    c[idx[bad]] = np.nan
    return c, removed


def _line_runs(score_line: np.ndarray, mask_line: np.ndarray, params: LaserDetectionParams) -> list[tuple]:
    """Candidate runs on one scan line: (centre, weight, width, peak). Runs wider than the limit are glare."""
    length = score_line.size
    out = []
    for start, stop in _segments(mask_line):
        width = stop - start
        if width > params.max_stripe_width_px:
            continue
        peak_i = start + int(np.argmax(np.nan_to_num(score_line[start:stop], nan=-1.0)))
        half = max(2, (width + 1) // 2 + 1)
        lo, hi = max(0, peak_i - half), min(length, peak_i + half + 1)
        window = score_line[lo:hi].astype(np.float64)
        if np.isnan(window).any():
            continue  # window touches excluded (dark) pixels: the centroid would be biased
        weights = np.clip(window - min(window[0], window[-1]), 0, None)  # remove local background
        total = weights.sum()
        if total <= 0:
            continue
        centre = float((weights * np.arange(lo, hi)).sum() / total)
        out.append((centre, float(np.nansum(score_line[start:stop])), width, float(np.nanmax(score_line[start:stop]))))
    return out


def _scan(score: np.ndarray, mask: np.ndarray, params: LaserDetectionParams):
    """Per scan line (rows of the given arrays): centre, confidence, width, multi-run flag.

    Lines with exactly one run are *anchors*. On lines with several candidate runs (reflections,
    glare) the run closest to the line interpolated between the nearest anchors is chosen,
    so the stripe is followed by continuity rather than by brightness alone.
    """
    n_lines = score.shape[0]
    m = mask > 0
    runs = [_line_runs(score[i], m[i], params) if m[i].any() else [] for i in range(n_lines)]
    centers = np.full(n_lines, np.nan)
    conf = np.zeros(n_lines)
    widths = np.zeros(n_lines)
    multi = np.zeros(n_lines, dtype=bool)
    anchor_idx, anchor_c = [], []
    for i, rl in enumerate(runs):
        if not rl:
            continue
        multi[i] = len(rl) > 1
        if not multi[i]:
            anchor_idx.append(i)
            anchor_c.append(rl[0][0])
    anchor_idx = np.asarray(anchor_idx)
    anchor_c = np.asarray(anchor_c)
    for i, rl in enumerate(runs):
        if not rl:
            continue
        if not multi[i] or anchor_idx.size == 0:
            chosen = max(rl, key=lambda r: r[1])
        else:
            k = np.searchsorted(anchor_idx, i)
            neighbours = [j for j in (k - 1, k) if 0 <= j < anchor_idx.size]
            if len(neighbours) == 2:
                a, b = neighbours
                t = (i - anchor_idx[a]) / max(anchor_idx[b] - anchor_idx[a], 1)
                ref = anchor_c[a] + t * (anchor_c[b] - anchor_c[a])
            else:
                ref = anchor_c[neighbours[0]]
            chosen = min(rl, key=lambda r: abs(r[0] - ref))
        total_w = sum(r[1] for r in rl)
        uniqueness = chosen[1] / total_w if total_w > 0 else 0.0
        strength = min(1.0, chosen[3] / (3.0 * params.threshold))
        centers[i] = chosen[0]
        widths[i] = chosen[2]
        conf[i] = float(np.clip(strength * (0.5 + 0.5 * uniqueness), 0.0, 1.0))
    return centers, conf, widths, multi


def detect_laser_stripe(image_bgr: np.ndarray, params: LaserDetectionParams, axis: str = "auto",
                        roi_mask: np.ndarray | None = None, background_bgr: np.ndarray | None = None) -> StripeResult:
    """Detect the red laser line and return sub-pixel centres along the chosen axis.

    ``background_bgr``: optional laser-OFF image of the same unmoved scene (see :func:`laser_only_image`).
    """
    if background_bgr is not None:
        diff, albedo = laser_only_image(image_bgr, background_bgr)
        score, saturated = compute_red_score(diff, params)
        score = np.clip(score / albedo, 0, 255).astype(np.float32)
        excluded = albedo < MIN_ALBEDO
    else:
        score, saturated = compute_red_score(image_bgr, params)
        excluded = None
    mask = threshold_mask(score, params, roi_mask)
    if excluded is not None:
        mask[excluded] = 0
        score = score.copy()
        score[excluded] = np.nan  # scan lines whose centroid window touches these are skipped
    h, w = mask.shape
    used_axis = choose_axis(mask) if axis == "auto" else axis
    if used_axis not in (AXIS_COLUMNS, AXIS_ROWS):
        raise ValueError(f"profile axis must be auto, {AXIS_COLUMNS} or {AXIS_ROWS}, got {axis!r}")
    if used_axis == AXIS_COLUMNS:
        s_lines, m_lines = score.T, mask.T
    else:
        s_lines, m_lines = score, mask
    raw, conf, widths, multi = _scan(np.ascontiguousarray(s_lines), np.ascontiguousarray(m_lines), params)
    centers, removed = reject_outliers(raw, params.outlier_threshold_px, params.neighbour_window)
    # Drop tiny isolated fragments.
    for start, stop in _segments(np.isfinite(centers)):
        if stop - start < params.min_segment_length:
            centers[start:stop] = np.nan
    centers = nan_median_filter(centers, int(params.smoothing_window))
    conf = np.where(np.isfinite(centers), conf, 0.0)
    positions = np.arange(len(centers))

    result = StripeResult(axis=used_axis, positions=positions, centers=centers, raw_centers=raw,
                          confidence=conf, widths=widths, score=np.nan_to_num(score), mask=mask, image_shape=(h, w),
                          outliers_removed=removed)
    valid = result.valid
    lines_with_any = np.isfinite(raw)
    result.multi_run_fraction = float(multi[lines_with_any].mean()) if lines_with_any.any() else 0.0
    laser_px = int((mask > 0).sum())
    result.saturated_fraction = float((saturated & (mask > 0)).sum() / laser_px) if laser_px else 0.0

    if not valid.any():
        result.warnings.append("No laser stripe was detected. Check that the laser is on, lower the Threshold, "
                               "or reduce room light.")
        return result
    if result.coverage < 0.3:
        result.warnings.append(f"The stripe covers only {result.coverage:.0%} of the image. Results may be unreliable.")
    if result.n_segments > 5:
        result.warnings.append(f"The stripe is broken into {result.n_segments} pieces (gaps, dark spots or reflections).")
    if result.multi_run_fraction > 0.2:
        result.warnings.append(f"{result.multi_run_fraction:.0%} of scan lines contain more than one red region: "
                               "possible reflections or glare. The strongest region was used.")
    if result.saturated_fraction > 0.3:
        result.warnings.append("The laser line is saturated (white core). Reduce laser power, exposure or gain for "
                               "better sub-pixel accuracy.")
    if removed > 0.1 * valid.sum():
        result.warnings.append(f"{removed} outlier points were removed. The stripe may be noisy.")
    return result
