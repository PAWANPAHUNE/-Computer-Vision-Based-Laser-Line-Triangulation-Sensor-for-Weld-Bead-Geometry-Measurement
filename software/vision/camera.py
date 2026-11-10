"""USB camera access via OpenCV (AVFoundation on macOS). Never crashes the app: errors are raised as CameraError."""
from __future__ import annotations

import platform
import time
from dataclasses import dataclass

import cv2
import numpy as np


class CameraError(RuntimeError):
    pass


def _backend_id(backend: str) -> int | None:
    if backend == "avfoundation":
        return cv2.CAP_AVFOUNDATION
    if backend == "default":
        return None
    return cv2.CAP_AVFOUNDATION if platform.system() == "Darwin" else None


def open_camera(index: int, backend: str = "auto", width: int | None = None, height: int | None = None) -> cv2.VideoCapture:
    api = _backend_id(backend)
    cap = cv2.VideoCapture(index, api) if api is not None else cv2.VideoCapture(index)
    if not cap.isOpened() and api is not None and backend == "auto":
        cap.release()
        cap = cv2.VideoCapture(index)
    if not cap.isOpened():
        cap.release()
        raise CameraError(f"Could not open camera index {index}. Try another index (Scan Cameras), check the USB "
                          "cable/adapter, and allow camera access for Terminal/VS Code in System Settings > Privacy & "
                          "Security > Camera.")
    if width and height:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, int(width))
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, int(height))
    return cap


def read_frame(cap: cv2.VideoCapture, warmup: int = 0) -> np.ndarray:
    for _ in range(max(0, warmup)):
        cap.read()
    ok, frame = cap.read()
    if not ok or frame is None:
        raise CameraError("The camera opened but returned no image. Close other apps using the camera and retry.")
    if float(frame.mean()) < 1.0:
        raise CameraError("The camera returned a black image. Check the lens cap, lighting and exposure, or wait a "
                          "second and capture again.")
    return frame


def grab_frame(index: int, backend: str = "auto", width: int | None = None, height: int | None = None,
               warmup: int = 5) -> np.ndarray:
    cap = open_camera(index, backend, width, height)
    try:
        return read_frame(cap, warmup)
    finally:
        cap.release()


@dataclass
class CameraInfo:
    index: int
    opened: bool
    width: int = 0
    height: int = 0
    message: str = ""


def scan_cameras(max_index: int = 5, backend: str = "auto") -> list[CameraInfo]:
    found = []
    for i in range(max_index):
        try:
            cap = open_camera(i, backend)
        except CameraError:
            found.append(CameraInfo(i, False, message="not available"))
            continue
        try:
            ok, frame = cap.read()
            if ok and frame is not None:
                found.append(CameraInfo(i, True, frame.shape[1], frame.shape[0], "ok"))
            else:
                found.append(CameraInfo(i, False, message="opened, no frames"))
        finally:
            cap.release()
        time.sleep(0.05)
    return found
