#!/usr/bin/env python3
"""Take calibration / test photos with the Arducam, named and sorted automatically.

    python scripts/capture_photos.py --mode checkerboard      # step 1: camera calibration (laser OFF)
    python scripts/capture_photos.py --mode laser             # step 2: laser plane (needs the finished fixture)
    python scripts/capture_photos.py --mode check             # step 3: one extra position for the accuracy check
    python scripts/capture_photos.py --mode weld              # step 4: welds / test pieces with the laser on

Options: --camera N (camera index, default from config.yaml; try 0, 1, 2), --out FOLDER (default photos/).
Keys in the camera window:
    checkerboard / weld : SPACE = take photo (always saved)      Q = quit
    laser / check       : O = photo with laser OFF, then L = photo with laser ON (nothing may move)   Q = quit
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

from calibration.checkerboard import CheckerboardSpec  # noqa: E402
from utils.config_loader import PROJECT_ROOT, load_config  # noqa: E402
from utils.photo_capture import (CHECKERBOARD_POSITIONS, FOLDERS, LASER_POSES, MIN_LASER_POSES, TARGET_VIEWS,  # noqa: E402
                                 check_board, check_laser_pair, next_index, save_png, write_info)
from vision.camera import CameraError, open_camera  # noqa: E402
from vision.laser_detection import LaserDetectionParams  # noqa: E402

WIN = "Capture - press Q to quit"


def put(img, text, y, color=(255, 255, 255), scale=0.7):
    cv2.putText(img, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), 5, cv2.LINE_AA)
    cv2.putText(img, text, (14, y), cv2.FONT_HERSHEY_SIMPLEX, scale, color, 2, cv2.LINE_AA)


def draw_grid(img, cells):
    h, w = img.shape[:2]
    x0, y0, s = w - 130, 20, 34
    for r in range(3):
        for c in range(3):
            col = (0, 200, 0) if (r, c) in cells else (60, 60, 60)
            cv2.rectangle(img, (x0 + c * s, y0 + r * s), (x0 + c * s + s - 4, y0 + r * s + s - 4), col, -1)
    put(img, "covered", y0 + 3 * s + 18, scale=0.5)


def main() -> int:
    cfg = load_config().config
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=list(FOLDERS), required=True)
    ap.add_argument("--camera", type=int, default=cfg["camera"]["device_index"])
    ap.add_argument("--out", default=str(PROJECT_ROOT / "photos"))
    ap.add_argument("--any-camera", action="store_true",
                    help="allow a camera whose resolution differs from config.yaml (normally refused: wrong camera)")
    a = ap.parse_args()
    spec = CheckerboardSpec.from_config(cfg)
    params = LaserDetectionParams.from_config(cfg["laser"])
    root = Path(a.out)
    folder = root / FOLDERS[a.mode]
    try:
        cap = open_camera(a.camera, cfg["camera"]["backend"], cfg["camera"]["resolution"]["width"],
                          cfg["camera"]["resolution"]["height"])
    except CameraError as exc:
        print(exc)
        return 1
    ok, frame = cap.read()
    if not ok or frame is None:
        print("Camera opened but gave no picture. Try another --camera number.")
        return 1
    size = (frame.shape[1], frame.shape[0])
    want = (cfg["camera"]["resolution"]["width"], cfg["camera"]["resolution"]["height"])
    print(f"Camera {a.camera}: {size[0]} x {size[1]}")
    if size != want and not a.any_camera:
        cap.release()
        print(f"\nSTOP: this camera gives {size[0]} x {size[1]}, but the Arducam gives {want[0]} x {want[1]}.")
        print("This is probably the MacBook's own camera. Run the command again with the other number,")
        print(f"for example --camera {1 if a.camera == 0 else 0}. Nothing was saved.")
        return 2
    write_info(root, a.mode, a.camera, size, spec)
    print(f"Saving into {folder}")

    cells_done: set = set()
    for p in sorted(folder.glob("view_*.png")) if a.mode == "checkerboard" else []:
        im = cv2.imread(str(p))
        if im is not None:
            chk = check_board(im, spec, fast=True)
            cells_done |= set(chk.cells)
    pending_off = None
    msg, msg_col = "", (255, 255, 255)
    frame_no = 0
    last_check = None
    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            print("Lost the camera picture.")
            break
        frame_no += 1
        view = frame.copy()
        if a.mode == "checkerboard":
            n = next_index(folder, r"view_(\d+)")
            if frame_no % 5 == 1 or last_check is None:
                last_check = check_board(frame, spec, fast=True)
            if last_check.found:
                cv2.drawChessboardCorners(view, spec.pattern, last_check.corners.astype(np.float32), True)
            tip = CHECKERBOARD_POSITIONS[(n - 1) % len(CHECKERBOARD_POSITIONS)]
            put(view, f"Photo {n} of {TARGET_VIEWS}:  {tip}", 32, (0, 255, 255))
            put(view, ("BOARD FOUND - hold still, press SPACE" if last_check.ok else
                       "Board not recognised yet - you can still press SPACE to save"),
                64, (0, 255, 0) if last_check.ok else (0, 165, 255))
            draw_grid(view, cells_done)
        elif a.mode in ("laser", "check"):
            stem = "pose" if a.mode == "laser" else "check"
            n = next_index(folder, rf"{stem}_(\d+)_laser_on")
            if a.mode == "laser":
                tip = LASER_POSES[(n - 1) % len(LASER_POSES)]
                put(view, f"Pose {n} (need at least {MIN_LASER_POSES}): {tip}", 32, (0, 255, 255))
            else:
                put(view, "Check: board in a NEW position (not used before), red line across the squares", 32, (0, 255, 255))
            put(view, "Laser OFF, press O" if pending_off is None else "Now laser ON - DON'T move anything - press L", 64,
                (0, 255, 0))
        else:
            n = next_index(folder, r"weld_(\d+)")
            put(view, f"Weld photo {n}: red line across the bead, press SPACE", 32, (0, 255, 255))
        if msg:
            put(view, msg, view.shape[0] - 24, msg_col, 0.65)
        cv2.imshow(WIN, view)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            break
        if a.mode == "checkerboard" and key == ord(" "):
            # Always save: photos where the board is not recognised are checked later.
            chk = check_board(frame, spec, fast=False)
            path = save_png(frame, folder / f"view_{n:02d}.png")
            if chk.found:
                cells_done |= set(chk.cells)
                msg, msg_col = f"Saved {path.name} - board found. Move to the next position.", (0, 255, 0)
            else:
                msg, msg_col = f"Saved {path.name} - board NOT recognised (will be checked later). Next position.", (0, 165, 255)
            print(msg)
        elif a.mode == "weld" and key == ord(" "):
            path = save_png(frame, folder / f"weld_{n:02d}.png")
            msg, msg_col = f"Saved {path.name}", (0, 255, 0)
            print(msg)
        elif a.mode in ("laser", "check") and key == ord("o"):
            chk = check_board(frame, spec, fast=False)
            if chk.found:
                pending_off = frame.copy()
                msg, msg_col = "Laser OFF photo OK. Switch the laser ON (don't touch the board), press L.", (0, 255, 0)
            else:
                msg, msg_col = "Board not found in the laser OFF photo - whole board must be visible.", (0, 0, 255)
            print(msg)
        elif a.mode in ("laser", "check") and key == ord("l"):
            if pending_off is None:
                msg, msg_col = "First take the laser OFF photo (press O).", (0, 0, 255)
            else:
                lc = check_laser_pair(pending_off, frame, params, spec=spec)
                if lc.ok:
                    save_png(pending_off, folder / f"{stem}_{n:02d}_laser_off.png")
                    save_png(frame, folder / f"{stem}_{n:02d}_laser_on.png")
                    msg, msg_col = f"Saved {stem} {n}. " + (lc.messages[0] if lc.messages else "Next position."), (0, 255, 0)
                    pending_off = None
                else:
                    msg, msg_col = "NOT saved: " + " ".join(lc.messages), (0, 0, 255)
                    pending_off = None
            print(msg)
    cap.release()
    cv2.destroyAllWindows()
    print(f"Photos are in {folder}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
