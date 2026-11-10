"""Capture-tool checks (no camera needed): board found / blurry / missing, laser pair OK / moved / no laser."""
from __future__ import annotations

import cv2
import numpy as np

from synthetic.demo import DEMO_SPEC, demo_rig
from synthetic.scene import look_at_pose, render_board_image
from utils.photo_capture import check_board, check_laser_pair, next_index, save_png, write_info


def board(d=170, tx=5, ty=-5, laser=False, seed=0, shift=(0.0, 0.0)):
    rv, tv = look_at_pose(d, tx, ty, DEMO_SPEC, shift)
    return render_board_image(demo_rig(), DEMO_SPEC, rv, tv, laser_on=laser, seed=seed)


def test_board_found_and_cells():
    chk = check_board(board(), DEMO_SPEC)
    assert chk.found and chk.ok and len(chk.cells) >= 1
    fast = check_board(board(), DEMO_SPEC, fast=True)
    assert fast.found
    assert np.max(np.abs(fast.corners.reshape(-1, 2) - chk.corners.reshape(-1, 2))) < 3.0


def test_board_missing_and_blurry():
    blank = np.full((800, 1280, 3), 120, np.uint8)
    assert not check_board(blank, DEMO_SPEC).found
    blurry = cv2.GaussianBlur(board(), (0, 0), 6)
    chk = check_board(blurry, DEMO_SPEC)
    assert chk.ok == chk.found          # blur is a warning only, never blocks a found board


def test_small_far_board_found_in_preview():
    far = board(d=330, tx=0, ty=0)
    assert check_board(far, DEMO_SPEC, fast=True).found


def test_laser_pair_ok():
    lc = check_laser_pair(board(seed=1), board(laser=True, seed=2))
    assert lc.ok, lc.messages


def test_laser_pair_moved_rejected():
    lc = check_laser_pair(board(seed=1), board(laser=True, seed=2, shift=(6.0, 0.0)))
    assert not lc.ok and any("MOVED" in m for m in lc.messages)


def test_laser_pair_without_laser_rejected():
    lc = check_laser_pair(board(seed=1), board(seed=2))
    assert not lc.ok and any("THE SAME" in m for m in lc.messages)


def test_laser_left_on_for_both_photos_is_explained():
    # Common beginner mistake: the laser stays ON for the "laser OFF" photo too.
    lc = check_laser_pair(board(laser=True, seed=1), board(laser=True, seed=2))
    assert not lc.ok and any("switched OFF" in m for m in lc.messages)


def _noisy_brighter(img, gain=1.15, noise=12, seed=3):
    rng = np.random.default_rng(seed)
    out = img.astype(np.float32) * gain + rng.normal(0, noise, img.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def test_auto_exposure_and_noise_are_not_movement():
    # Real camera: switching the laser changes the auto-exposure and a dark room adds sensor noise.
    off = _noisy_brighter(board(seed=1), gain=1.0, seed=4)
    on = _noisy_brighter(board(laser=True, seed=2), gain=1.15, seed=5)
    lc = check_laser_pair(off, on, spec=DEMO_SPEC)
    assert lc.ok, lc.messages


def test_board_shift_detected_from_corners():
    lc = check_laser_pair(board(seed=1), board(laser=True, seed=2, shift=(6.0, 0.0)), spec=DEMO_SPEC)
    assert not lc.ok and any("BOARD MOVED" in m for m in lc.messages)


def test_laser_left_on_with_spec_is_explained():
    lc = check_laser_pair(board(laser=True, seed=1), board(laser=True, seed=2), spec=DEMO_SPEC)
    assert not lc.ok and any("switched OFF" in m for m in lc.messages)


def test_naming_and_info(tmp_path):
    f = tmp_path / "1_checkerboard"
    assert next_index(f, r"view_(\d+)") == 1
    save_png(np.zeros((10, 10, 3), np.uint8), f / "view_01.png")
    save_png(np.zeros((10, 10, 3), np.uint8), f / "view_07.png")
    assert next_index(f, r"view_(\d+)") == 8
    p = write_info(tmp_path, "checkerboard", 1, (1280, 800), DEMO_SPEC)
    write_info(tmp_path, "laser", 1, (1280, 800), DEMO_SPEC)
    text = p.read_text()
    assert "9 x 6" in text and text.count("mode=") == 2 and "???" in text
