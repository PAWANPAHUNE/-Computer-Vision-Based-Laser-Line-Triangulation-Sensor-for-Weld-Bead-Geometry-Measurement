"""Laser-plane calibration with a checkerboard of KNOWN geometry.

Why this is metric
------------------
The checkerboard's square size is measured with a ruler, so its 3D geometry is known.
With calibrated intrinsics, ``cv2.solvePnP`` recovers the board's exact pose (rotation and
translation) in the camera frame for every placement. The target pose is therefore MEASURED
by the camera from the known pattern; the user never has to type positions or angles.

Procedure for each placement ("pose"):
1. Image A (laser OFF, or ON if corners are still found): detect the corners -> PnP pose ->
   board plane ``n . P + d = 0`` in the camera frame.
2. Image B (laser ON, nothing moved): subtract image A (removes the printed pattern) and divide by
   the board brightness (so black/white edges do not pull the stripe centre), detect the stripe only
   inside the projected board outline -> undistort -> camera rays -> intersect with the board plane -> 3D laser points.
3. The 3D points of one pose lie on a straight line (laser plane x board plane).

Lines from at least ``min_poses`` different placements (different distance and/or tilt)
span the laser plane. A robust SVD plane fit gives ``aX + bY + cZ + d = 0``.
Rejected when: too few poses/points, PnP error too high, a pose's points are not a line,
lines too close together (``min_pose_spread_mm``), plane RMS above ``max_plane_rms_mm``, or
the plane passes (almost) through the camera centre (triangulation impossible).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

from calibration.checkerboard import CheckerboardSpec, find_checkerboard
from calibration.triangulation import (board_plane_from_pose, fit_line_3d, robust_line_3d, normalize_plane,
                                       robust_fit_plane, triangulate_pixels)
from vision.laser_detection import LaserDetectionParams, detect_laser_stripe


@dataclass
class LaserPose:
    name: str
    ok: bool
    reason: str = ""
    rvec: np.ndarray | None = None
    tvec: np.ndarray | None = None
    pnp_error_px: float | None = None
    board_plane: np.ndarray | None = None
    points_3d: np.ndarray | None = None
    stripe_uv: np.ndarray | None = None
    line_rms_mm: float | None = None
    line_direction: np.ndarray | None = None
    distance_mm: float | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def n_points(self) -> int:
        return 0 if self.points_3d is None else int(len(self.points_3d))


def board_region_mask(image_size: tuple[int, int], spec: CheckerboardSpec, rvec, tvec, K, dist,
                      margin_mm: float) -> np.ndarray:
    """Mask of the board area (all printed squares + margin) as seen in the image."""
    outline = spec.outer_outline_mm(margin_mm)
    # Densify edges so lens distortion bends them correctly.
    pts = []
    for a, b in zip(outline, np.roll(outline, -1, axis=0)):
        for t in np.linspace(0, 1, 20, endpoint=False):
            pts.append(a + t * (b - a))
    proj, _ = cv2.projectPoints(np.array(pts), rvec, tvec, K, dist)
    mask = np.zeros((image_size[1], image_size[0]), np.uint8)
    cv2.fillPoly(mask, [np.round(proj.reshape(-1, 2)).astype(np.int32)], 255)
    return mask


def process_laser_pose(board_image: np.ndarray, laser_image: np.ndarray | None, camera_matrix: np.ndarray,
                       dist_coeffs: np.ndarray, calib_size: tuple[int, int], spec: CheckerboardSpec,
                       laser_params: LaserDetectionParams, policy: dict[str, Any], name: str,
                       min_angle_deg: float = 2.0) -> LaserPose:
    """Measure one board placement. ``laser_image=None`` means the board image also shows the laser."""
    if laser_image is None:
        laser_image = board_image
    for label, im in (("Laser OFF image", board_image), ("Laser ON image", laser_image)):
        if im is None:
            return LaserPose(name, False, f"{label} is missing.")
        size = (im.shape[1], im.shape[0])
        if size != tuple(calib_size):
            return LaserPose(name, False, f"{label} is {size[0]}x{size[1]} but the camera was calibrated at "
                                          f"{calib_size[0]}x{calib_size[1]}. Use the same resolution.")
    gray = cv2.cvtColor(board_image, cv2.COLOR_BGR2GRAY)
    found, corners = find_checkerboard(gray, spec)
    if not found:
        return LaserPose(name, False, "Checkerboard not found in the Laser OFF image. If the laser line hides "
                                      "corners, switch the laser off for this image.")
    objp = spec.object_points().astype(np.float64)
    ok, rvec, tvec = cv2.solvePnP(objp, corners.astype(np.float64), camera_matrix, dist_coeffs,
                                  flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return LaserPose(name, False, "Board pose could not be computed (solvePnP failed).")
    proj, _ = cv2.projectPoints(objp, rvec, tvec, camera_matrix, dist_coeffs)
    pnp_err = float(np.sqrt(np.mean(np.sum((proj.reshape(-1, 2) - corners.reshape(-1, 2)) ** 2, axis=1))))
    pose = LaserPose(name, False, rvec=rvec.reshape(3), tvec=tvec.reshape(3), pnp_error_px=pnp_err)
    if pnp_err > policy["max_pnp_reprojection_error_px"]:
        pose.reason = (f"Board pose error {pnp_err:.2f} px is above {policy['max_pnp_reprojection_error_px']} px. "
                       "Is the board flat? Was the camera recalibrated after a focus change?")
        return pose
    plane = board_plane_from_pose(rvec, tvec)
    pose.board_plane = plane
    pose.distance_mm = float(-plane[3])

    roi = board_region_mask(calib_size, spec, rvec, tvec, camera_matrix, dist_coeffs, policy["region_margin_mm"])
    background = board_image if laser_image is not board_image else None
    stripe = detect_laser_stripe(laser_image, laser_params, axis="auto", roi_mask=roi, background_bgr=background)
    uv = stripe.image_points()
    pose.stripe_uv = uv
    on_board = roi > 0
    if on_board.any():
        red = laser_image[..., 2][on_board & (stripe.mask > 0)]
        if red.size and float(np.mean(red >= laser_params.saturation_level)) > 0.3:
            pose.warnings.append("The laser line is saturated on the board. Lower the camera exposure or room light "
                                 "so the line is bright red, not white.")
    # Coverage/fragment warnings refer to the whole image; on a board region they are expected.
    pose.warnings.extend(w for w in stripe.warnings if not w.startswith(("The stripe covers only",
                                                                        "The stripe is broken")))
    if len(uv) < policy["min_points_per_pose"]:
        pose.reason = (f"Only {len(uv)} laser points found on the board (need {policy['min_points_per_pose']}). "
                       "Make sure the red line crosses the printed squares and is clearly visible.")
        return pose
    pts, reasons = triangulate_pixels(uv, camera_matrix, dist_coeffs, plane, min_angle_deg)
    pts = pts[np.all(np.isfinite(pts), axis=1)]
    if len(pts) < policy["min_points_per_pose"]:
        pose.reason = "Too few laser points could be projected onto the board plane."
        return pose
    # A few stray points where the laser leaves the board (edge, box, floor) must not reject a good pose;
    # a bent board or reflections still fail because then MOST points leave the line.
    inlier_mm = float(policy.get("line_inlier_threshold_mm", 1.5))
    min_frac = float(policy.get("min_line_inlier_fraction", 0.75))
    _, direction, line_rms, keep = robust_line_3d(pts, inlier_mm)
    frac = float(keep.mean())
    if frac < min_frac:
        _, direction, line_rms = fit_line_3d(pts)
        pose.points_3d, pose.line_rms_mm, pose.line_direction = pts, line_rms, direction
        pose.reason = (f"Only {frac:.0%} of the laser points on the board lie on one straight line (need "
                       f"{min_frac:.0%}). The board may be bent, or reflections were detected.")
        return pose
    if not keep.all():
        pose.warnings.append(f"{int((~keep).sum())} stray laser point(s) more than {inlier_mm:g} mm off the line "
                             "were ignored (usually where the line leaves the board).")
    pts = pts[keep]
    pose.points_3d, pose.line_rms_mm, pose.line_direction = pts, line_rms, direction
    if line_rms > policy["max_pose_line_rms_mm"]:
        pose.reason = (f"The laser points on the board are not a straight line (RMS {line_rms:.2f} mm > "
                       f"{policy['max_pose_line_rms_mm']} mm). The board may be bent, or reflections were detected.")
        return pose
    pose.ok = True
    return pose


@dataclass
class LaserPlaneResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    plane: np.ndarray | None = None
    rms_mm: float | None = None
    max_abs_mm: float | None = None
    num_points: int = 0
    num_poses: int = 0
    inlier_fraction: float = 0.0
    pose_spread_mm: float = 0.0
    depth_range_mm: tuple[float, float] | None = None
    per_pose_rms_mm: dict[str, float] = field(default_factory=dict)


def fit_laser_plane(poses: list[LaserPose], policy: dict[str, Any]) -> LaserPlaneResult:
    good = [p for p in poses if p.ok]
    res = LaserPlaneResult(ok=False, num_poses=len(good))
    if len(good) < policy["min_poses"]:
        res.errors.append(f"{len(good)} good pose(s); at least {policy['min_poses']} are needed. Add poses at "
                          "different distances and tilts.")
        return res
    all_pts = np.vstack([p.points_3d for p in good])
    owner = np.concatenate([[i] * p.n_points for i, p in enumerate(good)])
    fit = robust_fit_plane(all_pts)
    plane = fit.plane
    res.plane = plane
    res.rms_mm, res.max_abs_mm = fit.rms, fit.max_abs
    res.num_points = int(len(all_pts))
    res.inlier_fraction = float(fit.inliers.mean())
    res.depth_range_mm = (float(np.min(all_pts[:, 2])), float(np.max(all_pts[:, 2])))
    for i, p in enumerate(good):
        r = fit.residuals[owner == i]
        res.per_pose_rms_mm[p.name] = float(np.sqrt(np.mean(r ** 2)))

    # Spread of the pose lines across the plane (the plane is undetermined if all lines coincide).
    n = plane[:3]
    ref = good[0].line_direction
    dirs = []
    for p in good:
        d = p.line_direction - (p.line_direction @ n) * n
        d /= np.linalg.norm(d)
        dirs.append(d if d @ ref >= 0 else -d)
    u = np.mean(dirs, axis=0)
    u /= np.linalg.norm(u)
    w = np.cross(n, u)
    offsets = [float(p.points_3d.mean(axis=0) @ w) for p in good]
    res.pose_spread_mm = float(max(offsets) - min(offsets))

    if res.pose_spread_mm < policy["min_pose_spread_mm"]:
        res.errors.append(f"The laser lines from the poses are only {res.pose_spread_mm:.1f} mm apart across the "
                          f"laser plane (need {policy['min_pose_spread_mm']} mm). Move the board nearer/farther "
                          "or tilt it more between poses.")
    if abs(plane[3]) < policy["min_camera_to_plane_distance_mm"]:
        res.errors.append("The fitted laser plane passes through the camera. Triangulation is impossible with this "
                          "geometry: the camera and laser need a baseline.")
    if res.rms_mm > policy["max_plane_rms_mm"]:
        res.errors.append(f"Plane-fit RMS {res.rms_mm:.3f} mm is above {policy['max_plane_rms_mm']} mm. Check board "
                          "flatness, laser focus and that the laser did not move.")
    if res.inlier_fraction < 0.8:
        res.warnings.append(f"Only {res.inlier_fraction:.0%} of laser points agree with the plane.")
    res.ok = not res.errors
    if res.ok:
        res.plane = normalize_plane(plane)
    return res
