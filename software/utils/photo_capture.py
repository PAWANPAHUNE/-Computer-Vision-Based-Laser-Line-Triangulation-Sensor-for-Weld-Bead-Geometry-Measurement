"""Logic for the photo capture tool (scripts/capture_photos.py), kept free of GUI code so it can be tested.

Folder layout (inside photos/ in the project):
    1_checkerboard/   view_01.png ...            camera calibration (laser OFF)
    2_laser_plane/    pose_01_laser_off.png  pose_01_laser_on.png ...
    3_check/          check_01_laser_off.png check_01_laser_on.png   (new position, for the flat-plate check)
    4_weld/           weld_01.png ...            real welds / test pieces with the laser on
    INFO.txt          what was used (camera, resolution, board) + notes you add by hand
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from calibration.camera_calibration import MIN_SHARPNESS, grid_cells
from calibration.checkerboard import CheckerboardSpec, find_checkerboard, sharpness
from vision.laser_detection import LaserDetectionParams, compute_red_score, laser_only_image

FOLDERS = {"checkerboard": "1_checkerboard", "laser": "2_laser_plane", "check": "3_check", "weld": "4_weld"}

CHECKERBOARD_POSITIONS = [
    "centre of the picture, board flat (facing the camera)",
    "centre, board tilted LEFT about 30 degrees",
    "centre, board tilted RIGHT about 30 degrees",
    "centre, top edge tilted AWAY from the camera about 30 degrees",
    "centre, top edge tilted TOWARD the camera about 30 degrees",
    "TOP-LEFT corner of the picture",
    "TOP-RIGHT corner of the picture",
    "BOTTOM-LEFT corner of the picture",
    "BOTTOM-RIGHT corner of the picture",
    "TOP edge, middle",
    "BOTTOM edge, middle",
    "LEFT edge, middle",
    "RIGHT edge, middle",
    "CLOSER: board fills most of the picture (all corners still visible)",
    "FARTHER: board smaller, still sharp",
    "TOP-LEFT corner, board tilted",
    "BOTTOM-RIGHT corner, board tilted",
    "centre, board turned about 45 degrees (like a diamond)",
    "LEFT edge, board tilted",
    "RIGHT edge, board tilted",
]
TARGET_VIEWS = len(CHECKERBOARD_POSITIONS)

LASER_POSES = [
    "board flat on the table at the working distance, red line across the squares",
    "board about 2 cm HIGHER (put a book under it), tilted about 10 degrees",
    "board about 2 cm LOWER than pose 1, tilted about 10 degrees the other way",
    "board at the working distance, tilted about 15 degrees sideways",
    "board about 4 cm higher, flat",
    "board at the working distance, tilted about 15 degrees the other way",
]
MIN_LASER_POSES = 4


def next_index(folder: Path, pattern: str) -> int:
    """Next free number for files like view_07.png (pattern 'view_(\\d+)')."""
    nums = [int(m.group(1)) for p in folder.glob("*.png") if (m := re.match(pattern, p.stem))]
    return max(nums, default=0) + 1


def save_png(image: np.ndarray, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Could not save {path}")
    return path


@dataclass
class BoardCheck:
    found: bool
    corners: np.ndarray | None
    sharp: float
    cells: frozenset = frozenset()
    messages: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        # Sharpness is only a warning: a plain checkerboard can score low even when it is sharp.
        return self.found


def check_board(frame: np.ndarray, spec: CheckerboardSpec, fast: bool = False) -> BoardCheck:
    """Find the board. fast=True searches a half-size copy (live preview); the saved photo is checked at full size."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    sharp = sharpness(gray)
    scale = 0.5 if fast else 1.0
    g = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if fast else gray
    found, corners = find_checkerboard(g, spec)
    if fast and not found:   # a small/far board can be missed at half size: retry at full size
        scale, g = 1.0, gray
        found, corners = find_checkerboard(g, spec)
    msgs = []
    cells = frozenset()
    if found:
        corners = corners / scale
        cells = grid_cells(corners.reshape(-1, 2), (frame.shape[1], frame.shape[0]))
        if sharp < MIN_SHARPNESS:
            msgs.append("Board found (picture may be a little soft - hold still)")
    else:
        msgs.append(f"Board NOT found: all {spec.inner_corners_cols} x {spec.inner_corners_rows} inner corners must be "
                    "visible, sharp, no glare")
    return BoardCheck(found, corners, sharp, cells, msgs)


@dataclass
class LaserCheck:
    ok: bool
    red_pixels: int
    saturated_fraction: float
    messages: list[str] = field(default_factory=list)


def check_laser_pair(laser_off: np.ndarray, laser_on: np.ndarray, params: LaserDetectionParams | None = None,
                     min_pixels: int = 150, spec: CheckerboardSpec | None = None,
                     max_corner_shift_px: float = 1.0) -> LaserCheck:
    """Is there a clear red line in ON that is not in OFF, and did nothing move between the two photos?

    Movement is judged from the checkerboard corners when ``spec`` is given and the board is found in both
    photos: the camera's automatic brightness and the sensor noise in a dark room then cannot cause a false
    "moved" alarm. Otherwise a brightness-normalised, smoothed image comparison is used.
    """
    params = params or LaserDetectionParams()
    msgs = []
    if laser_off.shape != laser_on.shape:
        return LaserCheck(False, 0, 0.0, ["The two photos have different sizes."])
    diff_img, _ = laser_only_image(laser_on, laser_off)
    score, _ = compute_red_score(diff_img, params)
    red = score >= params.threshold
    n_red = int(red.sum())
    # Smoothed, brightness-matched comparison outside the red areas (noise and auto-exposure tolerant).
    g_off = cv2.GaussianBlur(cv2.cvtColor(laser_off, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 2.0)
    g_on = cv2.GaussianBlur(cv2.cvtColor(laser_on, cv2.COLOR_BGR2GRAY).astype(np.float32), (0, 0), 2.0)
    not_red = ~cv2.dilate(red.astype(np.uint8), np.ones((15, 15), np.uint8)).astype(bool)
    if not_red.any():
        gain = float(np.median(g_off[not_red]) / max(np.median(g_on[not_red]), 1.0))
        d = np.abs(g_on * gain - g_off)[not_red]
        moved = float(np.median(d))
        big_change = float(np.mean(d > 40))
    else:
        moved = big_change = 0.0
    corner_shift = None
    if spec is not None:
        b_off, b_on = check_board(laser_off, spec), check_board(laser_on, spec)
        if b_off.found and b_on.found:
            corner_shift = float(np.mean(np.linalg.norm(
                b_off.corners.reshape(-1, 2) - b_on.corners.reshape(-1, 2), axis=1)))
    sat = float(np.mean(laser_on[..., 2][red] >= params.saturation_level)) if n_red else 0.0
    ok = True
    if n_red < min_pixels:
        ok = False
        same = (corner_shift is not None and corner_shift < 0.3 and moved <= 3) or (moved <= 2 and big_change < 0.005)
        if same:
            # Both photos are practically identical: the laser was ON (or OFF) in both of them.
            msgs.append("The O and L photos look THE SAME. The O photo must be taken with the laser switched OFF, "
                        "the L photo with it ON. Press O again with the laser OFF.")
        else:
            msgs.append("No clear red line found. Is the laser ON and crossing the board? Darken the room a little.")
    if corner_shift is not None:
        if corner_shift > max_corner_shift_px:
            ok = False
            msgs.append(f"The BOARD MOVED by {corner_shift:.1f} px between the two photos. Take both photos again "
                        "without touching the board.")
    elif big_change > 0.02 or moved > 6:
        ok = False
        msgs.append("Something MOVED between the two photos (or the room light changed). Take both photos again.")
    if sat > 0.3:
        msgs.append("The red line is WHITE in the middle (too bright). Dim the room light or the laser if you can.")
    return LaserCheck(ok, n_red, sat, msgs)


def write_info(root: Path, mode: str, camera_index: int, size: tuple[int, int], spec: CheckerboardSpec) -> Path:
    path = root / "INFO.txt"
    root.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "PHOTO SESSION INFO\n"
            "Fill in the lines marked ??? by hand (measure with a ruler).\n\n"
            f"Checkerboard inner corners: {spec.inner_corners_cols} x {spec.inner_corners_rows}\n"
            f"Checkerboard square size in config: {spec.square_size_mm:g} mm\n"
            "Measured square size (4 squares / 4): ??? mm\n"
            "Working distance (fixture plate to metal): ??? mm\n"
            "Camera angle plate used (deg): ???\n"
            "Lens focus changed since the checkerboard photos? (yes/no): ???\n\n"
            "Session log:\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M}  mode={mode}  camera_index={camera_index}  "
                f"resolution={size[0]}x{size[1]}\n")
    return path
