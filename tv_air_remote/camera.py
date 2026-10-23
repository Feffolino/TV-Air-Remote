"""Frame capture from the webcam."""

from __future__ import annotations

import sys
import time

import cv2
import numpy as np


class CameraError(RuntimeError):
    """Webcam missing or not working."""


def _open(index: int) -> cv2.VideoCapture:
    if sys.platform == "win32":
        # Media Foundation, the default backend on Windows, takes 10-30 s
        # to open the webcam; DirectShow takes 1-2 s.
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap
        cap.release()
    return cv2.VideoCapture(index)


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30) -> None:
        self._cap = _open(index)
        if not self._cap.isOpened():
            self._cap.release()
            raise CameraError(
                f"Cannot open the webcam with index {index}. "
                "Try another index with --camera N."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> tuple[np.ndarray, int] | None:
        """Mirrored frame (user's left = left on screen) and monotonic
        timestamp in ms, or None if the read fails."""
        ok, frame = self._cap.read()
        if not ok:
            return None
        return cv2.flip(frame, 1), int(time.monotonic() * 1000)

    def close(self) -> None:
        self._cap.release()
