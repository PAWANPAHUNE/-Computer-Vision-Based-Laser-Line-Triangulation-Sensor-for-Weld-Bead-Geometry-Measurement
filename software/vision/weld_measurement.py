"""Weld bead width / height from a 2D profile (works in pixels or millimetres).

Input: a profile ``(x, y)`` sampled along the laser line, where ``x`` runs along the
line (across the bead) and ``y`` is the displacement that the bead causes
(stripe displacement in pixels, or height inside the laser plane in mm).

Algorithm
---------
1. Noise ``sigma`` from the median absolute second difference (robust to slopes).
2. Base-material reference line by RANSAC (deterministic seed), inlier band
   ``tau = max(3*sigma, 0.25*min_bead_height)``. The bead does not need to be centred.
3. Bead side: in ``auto`` the side with the larger summed out-of-band residual.
4. Bead core: the connected run of points more than ``max(tau, 0.5*min_bead_height)``
   above the reference with the largest area (gaps up to ``gap_tolerance`` points are bridged).
5. Bead edges: walk outward until the height drops to
   ``max(1.5*sigma, boundary_fraction*peak)``; interpolate the crossing linearly. Gaps (missing
   points) are crossed when the bead continues on the far side; an edge hidden inside a long gap
   is reported as a lower bound.
6. ``local_background``: refit the reference line using only flank points just outside
   both edges, then repeat 4-5 once. ``global_line``: keep the RANSAC line.
7. Width = edge distance measured ALONG the reference line. Height = largest
   perpendicular distance from the reference line. Area = integral of height.

Confidence (0-1) = sides x detect^0.4 x coverage^0.3 x snr^0.3, where *sides* is 1.0
with base material on both sides, 0.6 with one side, 0 with none.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

MIN_POINTS = 10
_trapezoid = getattr(np, "trapezoid", None) or np.trapz  # numpy < 2.0 compatibility
MIN_FLANK_POINTS = 5
MIN_BEAD_POINTS = 5     # fewer points above the surface = a spike, not an object


@dataclass
class MeasurementSettings:
    units: str = "px"
    min_bead_height: float = 3.0
    boundary_fraction: float = 0.05
    reference_surface: str = "local_background"
    bead_direction: str = "auto"          # auto | positive | negative
    gap_tolerance: int = 5
    peak_smoothing: int = 1               # odd; >1 = height from a moving median (ignores single-point spikes)
    ransac_iterations: int = 300


@dataclass
class WeldMeasurement:
    units: str
    status: str                            # ok | no_bead | insufficient_data
    width: float | None = None
    height: float | None = None
    area: float | None = None
    peak_x: float | None = None
    peak_y: float | None = None
    left_boundary_x: float | None = None
    right_boundary_x: float | None = None
    left_boundary_y: float | None = None
    right_boundary_y: float | None = None
    base_slope: float | None = None
    base_intercept: float | None = None
    base_rms: float | None = None
    noise_sigma: float | None = None
    bead_sign: int = 1
    base_points_left: int = 0
    base_points_right: int = 0
    confidence: float = 0.0
    confidence_parts: dict[str, float] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    height_curve: list[float] | None = None   # signed height above reference per input point (NaN invalid)

    def to_dict(self, include_curve: bool = False) -> dict[str, Any]:
        d = asdict(self)
        if not include_curve:
            d.pop("height_curve", None)
        return d


def estimate_noise(y: np.ndarray) -> float:
    y = y[np.isfinite(y)]
    if y.size < 5:
        return 0.0
    d2 = np.diff(y, 2)
    mad = np.median(np.abs(d2 - np.median(d2)))
    return float(1.4826 * mad / np.sqrt(6.0))


def _fit_line(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    if x.size < 2 or np.ptp(x) == 0:
        return 0.0, float(np.mean(y)) if y.size else 0.0
    m, c = np.polyfit(x, y, 1)
    return float(m), float(c)


def ransac_line(x: np.ndarray, y: np.ndarray, tau: float, iterations: int, seed: int = 0) -> tuple[float, float, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = x.size
    span = float(np.ptp(x)) if n else 0.0
    best = (-1, np.inf, 0.0, float(np.median(y)) if n else 0.0)
    for _ in range(iterations):
        i, j = rng.choice(n, 2, replace=False)
        if abs(x[j] - x[i]) < 0.05 * span:
            continue
        m = (y[j] - y[i]) / (x[j] - x[i])
        c = y[i] - m * x[i]
        r = np.abs(y - (m * x + c))
        inl = r < tau
        count = int(inl.sum())
        rms = float(np.sqrt(np.mean(r[inl] ** 2))) if count else np.inf
        if count > best[0] or (count == best[0] and rms < best[1]):
            best = (count, rms, m, c)
    _, _, m, c = best
    inliers = np.abs(y - (m * x + c)) < tau
    if inliers.sum() >= 2:
        m, c = _fit_line(x[inliers], y[inliers])
        inliers = np.abs(y - (m * x + c)) < tau
    return m, c, inliers


def _runs(flags: np.ndarray, gap: int) -> list[tuple[int, int]]:
    """Runs of True (inclusive start, exclusive stop), bridging False gaps of length <= gap."""
    idx = np.nonzero(flags)[0]
    if idx.size == 0:
        return []
    runs = []
    start = prev = idx[0]
    for k in idx[1:]:
        if k - prev - 1 > gap:
            runs.append((start, prev + 1))
            start = k
        prev = k
    runs.append((start, prev + 1))
    return runs


def _find_bead(x, rs, valid, tau_high, low, gap):
    """Return (core_start, core_stop, left_x, right_x, peak_idx, touches_edge) in index space or None."""
    cand = valid & (rs > tau_high)
    runs = _runs(cand, gap)
    if not runs:
        return None
    areas = [np.nansum(np.where(valid[a:b], rs[a:b], 0.0)) for a, b in runs]
    a, b = runs[int(np.argmax(areas))]
    seg = np.where(valid[a:b], rs[a:b], -np.inf)
    peak_idx = a + int(np.argmax(seg))
    vidx = np.nonzero(valid)[0]

    def walk(direction: int) -> tuple[float, bool]:
        pos = np.searchsorted(vidx, peak_idx)
        last_above = peak_idx
        k = pos
        while True:
            k += direction
            if k < 0 or k >= vidx.size:
                return float(x[last_above]), True
            i = vidx[k]
            long_gap = abs(i - last_above) - 1 > gap
            if long_gap and rs[i] <= low:
                # The edge lies somewhere inside missing data: report the last measured bead point.
                return float(x[last_above]), True
            if rs[i] <= low:
                # linear interpolation between last_above (above low) and i (at/below low)
                ra, rb = rs[last_above], rs[i]
                t = (ra - low) / (ra - rb) if ra != rb else 0.0
                return float(x[last_above] + t * (x[i] - x[last_above])), False
            last_above = i

    left_x, left_edge = walk(-1)
    right_x, right_edge = walk(+1)
    return a, b, min(left_x, right_x), max(left_x, right_x), peak_idx, (left_edge or right_edge)


def measure_profile(x: np.ndarray, y: np.ndarray, settings: MeasurementSettings,
                    point_confidence: np.ndarray | None = None) -> WeldMeasurement:
    """Measure one bead in a profile. ``y`` may contain NaN for missing points.

    ``x`` must be monotonic (sorted along the laser line).
    """
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if point_confidence is None:
        point_confidence = np.ones_like(y)
    valid = np.isfinite(x) & np.isfinite(y)
    out = WeldMeasurement(units=settings.units, status="insufficient_data")
    if valid.sum() < MIN_POINTS:
        out.warnings.append(f"Only {int(valid.sum())} valid profile points; at least {MIN_POINTS} are needed.")
        return out
    xv, yv = x[valid], y[valid]
    sigma = estimate_noise(yv)
    floor = 0.25 * settings.min_bead_height
    tau = max(3.0 * sigma, floor)
    m, c, inliers = ransac_line(xv, yv, tau, settings.ransac_iterations)
    out.noise_sigma = sigma

    r = y - (m * x + c)
    if settings.bead_direction == "positive":
        sign = 1
    elif settings.bead_direction == "negative":
        sign = -1
    else:
        rv = r[valid]
        pos = float(np.sum(rv[rv > tau])) if np.any(rv > tau) else 0.0
        neg = float(np.sum(-rv[rv < -tau])) if np.any(rv < -tau) else 0.0
        sign = 1 if pos >= neg else -1
    out.bead_sign = sign

    tau_high = max(tau, 0.5 * settings.min_bead_height)
    bead = None
    for _ in range(2):
        rs = sign * (y - (m * x + c))
        rs_v = np.where(valid, rs, np.nan)
        peak_guess = np.nanmax(rs_v) if np.any(np.isfinite(rs_v)) else 0.0
        low = max(1.5 * sigma, settings.boundary_fraction * max(peak_guess, 0.0))
        bead = _find_bead(x, np.nan_to_num(rs_v, nan=-np.inf), valid, tau_high, low, settings.gap_tolerance)
        if bead is None:
            break
        _, _, lx, rx, _, _ = bead
        # Reference line from base points outside the bead.
        bw = rx - lx
        span = float(np.ptp(xv))
        guard = 0.1 * bw
        outside = valid & ((x < lx - guard) | (x > rx + guard)) & (np.abs(y - (m * x + c)) < tau)
        if settings.reference_surface == "local_background":
            flank = max(0.5 * bw, 0.1 * span)
            near = (x >= lx - guard - flank) & (x <= rx + guard + flank)
            sel = outside & near
            if sel.sum() < 2 * MIN_FLANK_POINTS:
                sel = outside
        else:
            sel = outside
        if sel.sum() >= 2:
            m, c = _fit_line(x[sel], y[sel])

    rs = sign * (y - (m * x + c))
    out.base_slope, out.base_intercept = m, c
    out.height_curve = [float(v) if valid[i] else float("nan") for i, v in enumerate(rs)]
    if bead is None:
        out.status = "no_bead"
        out.warnings.append("No bead found above the reference line (nothing rises more than the minimum bead height).")
        return out
    a, b, lx, rx, peak_idx, touches = bead
    n_core = int((valid & (x >= lx) & (x <= rx)).sum())
    if n_core < MIN_BEAD_POINTS:
        out.status = "no_bead"
        out.warnings.append(f"Only {n_core} point(s) rise above the surface - a stray red dot or reflection, not an "
                            "object. Make sure the red line runs across the object (floor - object - floor).")
        return out
    peak = float(rs[peak_idx])
    w = int(settings.peak_smoothing)
    if w > 1:
        # Height from a moving median inside the bead core: a single noisy point cannot set the height.
        core = np.arange(a, b + 1)
        core = core[valid[core]]
        if core.size >= w:
            vals = rs[core]
            half = w // 2
            med = np.array([np.median(vals[max(0, i - half):i + half + 1]) for i in range(vals.size)])
            j = int(np.argmax(med))
            peak, peak_idx = float(med[j]), int(core[j])
    if peak < settings.min_bead_height:
        out.status = "no_bead"
        out.warnings.append(f"Highest point is {peak:.3g} {settings.units} above the reference, below the minimum "
                            f"bead height {settings.min_bead_height:g} {settings.units}.")
        return out

    norm = float(np.sqrt(1.0 + m * m))
    bw = rx - lx
    guard = 0.1 * bw
    base_pts = valid & ((x < lx - guard) | (x > rx + guard)) & (np.abs(rs) < tau)
    left_n = int((base_pts & (x < lx)).sum())
    right_n = int((base_pts & (x > rx)).sum())
    base_res = rs[base_pts]
    base_rms = float(np.sqrt(np.mean(base_res ** 2))) if base_res.size else float("nan")
    inside = valid & (x >= lx) & (x <= rx)
    xi, ri = x[inside], np.clip(rs[inside], 0, None)
    area = float(_trapezoid(ri, xi)) if xi.size >= 2 else 0.0

    out.status = "ok"
    out.width = float(bw * norm)
    out.height = float(peak / norm)
    out.area = area
    out.peak_x = float(x[peak_idx])
    out.peak_y = float(y[peak_idx])
    out.left_boundary_x, out.right_boundary_x = float(lx), float(rx)
    out.left_boundary_y = float(m * lx + c)
    out.right_boundary_y = float(m * rx + c)
    out.base_rms = base_rms
    out.base_points_left, out.base_points_right = left_n, right_n

    if left_n < MIN_FLANK_POINTS or right_n < MIN_FLANK_POINTS:
        side = "left" if left_n < MIN_FLANK_POINTS else "right"
        out.warnings.append(f"Little or no base material visible on the {side} side of the bead; the reference "
                            "line is less reliable. Centre the bead in the laser line.")
    if touches:
        out.warnings.append("A bead edge reaches the end of the profile or lies inside missing data. The width is a "
                            "lower bound.")

    sides = 1.0 if (left_n >= MIN_FLANK_POINTS and right_n >= MIN_FLANK_POINTS) else \
        (0.6 if (left_n >= MIN_FLANK_POINTS or right_n >= MIN_FLANK_POINTS) else 0.0)
    span_lo, span_hi = lx - max(0.5 * bw, 1e-9), rx + max(0.5 * bw, 1e-9)
    region = np.isfinite(x) & (x >= span_lo) & (x <= span_hi)
    # Coverage in index space (missing points have finite x only if the caller provides it).
    idx = np.nonzero(region | (valid & (x >= span_lo) & (x <= span_hi)))[0]
    if idx.size:
        lo_i, hi_i = idx.min(), idx.max()
        coverage = float(valid[lo_i:hi_i + 1].mean())
        detect = float(np.mean(point_confidence[lo_i:hi_i + 1][valid[lo_i:hi_i + 1]]))
    else:
        coverage, detect = 0.0, 0.0
    noise_ref = max(base_rms if np.isfinite(base_rms) else 0.0, sigma, 1e-12)
    snr = float(np.clip((peak / noise_ref - 3.0) / 7.0, 0.0, 1.0))
    conf = sides * (max(detect, 0.0) ** 0.4) * (coverage ** 0.3) * (snr ** 0.3)
    out.confidence = float(np.clip(conf, 0.0, 1.0))
    out.confidence_parts = {"base_sides": sides, "detection": round(detect, 4), "coverage": round(coverage, 4),
                            "signal_to_noise": round(snr, 4)}
    return out
