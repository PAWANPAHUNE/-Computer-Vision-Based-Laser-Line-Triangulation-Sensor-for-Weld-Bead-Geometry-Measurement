"""Triangulation mathematics with known synthetic geometry."""
from __future__ import annotations

import math

import cv2
import numpy as np
import pytest

from calibration.nominal_model import (build_nominal_model, laser_plane_rig, missing_nominal_parameters,
                                       plane_rig_to_camera, rig_to_camera_rotation)
from calibration.triangulation import (REASON_BEHIND, REASON_DEPTH, REASON_OK, REASON_PARALLEL, DegeneratePlaneError,
                                       board_plane_from_pose, fit_line_3d, fit_plane, intersect_rays_with_plane,
                                       normalize_plane, point_plane_distances, points_to_plane_profile,
                                       robust_fit_plane, scale_intrinsics, triangulate_pixels)

K = np.array([[1000.0, 0, 639.5], [0, 1000.0, 399.5], [0, 0, 1]])


def test_normalize_plane_unit_normal_and_sign():
    p = normalize_plane([0, 0, 2, -400])
    assert np.allclose(p, [0, 0, 1, -200])
    q = normalize_plane([0, 0, -3, 600])
    assert np.allclose(q, [0, 0, 1, -200])
    assert np.isclose(np.linalg.norm(p[:3]), 1.0)


@pytest.mark.parametrize("bad", [[0, 0, 0, 1], [np.nan, 0, 1, 1], [1, 2, 3]])
def test_normalize_plane_rejects_invalid(bad):
    with pytest.raises(DegeneratePlaneError):
        normalize_plane(bad)


def test_ray_plane_known_intersection():
    plane = [0, 0, 1, -250]  # Z = 250
    rays = np.array([[0, 0, 1], [0.1, -0.2, 1]], float)
    pts, why = intersect_rays_with_plane(rays, plane)
    assert list(why) == [REASON_OK, REASON_OK]
    assert np.allclose(pts, [[0, 0, 250], [25, -50, 250]])


def test_ray_parallel_to_plane_rejected():
    plane = [1, 0, 0, -50]  # X = 50, contains direction (0,0,1)
    pts, why = intersect_rays_with_plane(np.array([[0, 0, 1.0]]), plane, min_angle_deg=2)
    assert why[0] == REASON_PARALLEL and np.all(np.isnan(pts[0]))


def test_ray_nearly_parallel_rejected_by_angle():
    plane = [1, 0, 0, -50]
    ray = np.array([[math.tan(math.radians(1.0)), 0, 1.0]])  # 1 deg from the plane
    _, why = intersect_rays_with_plane(ray, plane, min_angle_deg=2)
    assert why[0] == REASON_PARALLEL
    _, why = intersect_rays_with_plane(ray, plane, min_angle_deg=0.5)
    assert why[0] == REASON_OK


def test_intersection_behind_camera_rejected():
    pts, why = intersect_rays_with_plane(np.array([[0, 0, 1.0]]), [0, 0, 1, 100])  # Z = -100
    assert why[0] == REASON_BEHIND and np.all(np.isnan(pts))


def test_triangulate_roundtrip_with_distortion():
    dist = np.array([-0.15, 0.06, 0.001, -0.0007, 0.0])
    plane = normalize_plane([0.9, 0.05, 0.4, -80])
    # 3D points on the plane, in front of the camera
    rng = np.random.default_rng(0)
    pts = []
    while len(pts) < 50:
        y, z = rng.uniform(-40, 40), rng.uniform(150, 250)
        x = -(plane[1] * y + plane[2] * z + plane[3]) / plane[0]
        pts.append([x, y, z])
    pts = np.array(pts)
    uv, _ = cv2.projectPoints(pts.reshape(-1, 1, 3), np.zeros(3), np.zeros(3), K, dist)
    rec, why = triangulate_pixels(uv.reshape(-1, 2), K, dist, plane)
    assert np.all(why == REASON_OK)
    assert np.max(np.linalg.norm(rec - pts, axis=1)) < 1e-3


def test_triangulate_nan_and_depth_window():
    plane = [0, 0, 1, -300]
    uv = np.array([[640, 400], [np.nan, np.nan]])
    pts, why = triangulate_pixels(uv, K, np.zeros(5), plane, depth_range_mm=(20, 200))
    assert why[0] == REASON_DEPTH and why[1] == "no_stripe"
    assert np.all(np.isnan(pts))


def test_board_plane_from_pose():
    rvec = np.array([0.2, -0.1, 0.05])
    tvec = np.array([10.0, -5.0, 300.0])
    plane = board_plane_from_pose(rvec, tvec)
    R, _ = cv2.Rodrigues(rvec)
    corners = (R @ np.array([[0, 0, 0], [100, 0, 0], [0, 70, 0]]).T).T + tvec
    assert np.max(np.abs(point_plane_distances(corners, plane))) < 1e-9


def test_fit_plane_exact_and_robust():
    rng = np.random.default_rng(1)
    true = normalize_plane([0.3, -0.2, 0.93, -120])
    xy = rng.uniform(-50, 50, (300, 2))
    z = -(true[0] * xy[:, 0] + true[1] * xy[:, 1] + true[3]) / true[2]
    pts = np.column_stack([xy, z]) + rng.normal(0, 0.02, (300, 3))
    fit = fit_plane(pts)
    assert math.degrees(math.acos(abs(fit.plane[:3] @ true[:3]))) < 0.05
    assert fit.rms < 0.05
    pts[:20, 2] += 15  # gross outliers
    rob = robust_fit_plane(pts)
    assert math.degrees(math.acos(abs(rob.plane[:3] @ true[:3]))) < 0.1
    assert rob.inliers[:20].sum() == 0


def test_fit_plane_needs_three_points():
    with pytest.raises(DegeneratePlaneError):
        fit_plane(np.zeros((2, 3)))


def test_fit_line_3d():
    t = np.linspace(-10, 10, 50)
    pts = np.column_stack([t, 2 * t, 100 + 0.5 * t])
    _, d, rms = fit_line_3d(pts)
    assert rms < 1e-9 and abs(abs(d @ np.array([1, 2, 0.5]) / np.linalg.norm([1, 2, 0.5])) - 1) < 1e-9


def test_plane_profile_orientation():
    plane = normalize_plane([1, 0, 0, -50])  # X = 50 plane; points vary in Y (line) and Z (height)
    ys = np.linspace(-20, 20, 41)
    zs = np.full_like(ys, 200.0)
    zs[18:23] = 197.0  # 3 mm closer to the camera = bead
    pts = np.column_stack([np.full_like(ys, 50.0), ys, zs])
    prof = points_to_plane_profile(pts, plane)
    assert np.all(np.diff(prof.s) > 0)                       # s follows input order
    assert prof.h[20] - prof.h[0] == pytest.approx(3.0, abs=1e-9)  # toward the camera is positive


def test_scale_intrinsics_halving():
    K2 = scale_intrinsics(K, (1280, 800), (640, 400))
    assert K2[0, 0] == pytest.approx(500.0)
    assert K2[0, 2] == pytest.approx((639.5 + 0.5) / 2 - 0.5)


def test_nominal_model_geometry():
    # Pitch 0, laser angle 0: laser plane is X_rig = baseline = X_camera.
    R = rig_to_camera_rotation(0, 0, 0)
    plane = plane_rig_to_camera(laser_plane_rig(55.0, 0.0), R)
    assert np.allclose(plane, [1, 0, 0, -55])
    # Pitch toward the laser: the optical axis meets the laser plane at distance baseline / sin(pitch)
    R = rig_to_camera_rotation(20, 0, 0)
    plane = plane_rig_to_camera(laser_plane_rig(55.0, 0.0), R)
    t = -plane[3] / plane[2]
    assert t == pytest.approx(55.0 / math.sin(math.radians(20)), rel=1e-9)


def test_nominal_model_lists_missing_parameters(cfg):
    missing = missing_nominal_parameters(cfg)
    assert "camera.focal_length_mm" in missing and "geometry.camera_pitch_deg" in missing
    with pytest.raises(ValueError):
        build_nominal_model(cfg, (1280, 800))
