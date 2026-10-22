"""Acquisizione dei frame dalla webcam."""

from __future__ import annotations

import time

import cv2
import numpy as np


class CameraError(RuntimeError):
    """Webcam assente o non funzionante."""


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30) -> None:
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            self._cap.release()
            raise CameraError(
                f"Impossibile aprire la webcam con indice {index}. "
                "Prova un altro indice con --camera N."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> tuple[np.ndarray, int] | None:
        """Frame specchiato (sinistra dell'utente = sinistra a schermo) e
        timestamp monotono in ms, oppure None se la lettura fallisce."""
        ok, frame = self._cap.read()
        if not ok:
            return None
        return cv2.flip(frame, 1), int(time.monotonic() * 1000)

    def close(self) -> None:
        self._cap.release()
