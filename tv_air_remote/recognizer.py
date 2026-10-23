"""Riconoscimento delle gesture con MediaPipe Gesture Recognizer."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .observation import HandObservation

log = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float16/latest/gesture_recognizer.task"
)
DEFAULT_MODEL_PATH = Path("models") / "gesture_recognizer.task"


class ModelError(RuntimeError):
    """Modello assente e impossibile da scaricare."""


def ensure_model(path: Path = DEFAULT_MODEL_PATH, url: str = MODEL_URL) -> Path:
    """Restituisce il percorso del modello, scaricandolo se manca."""
    path = Path(path)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    log.info("Downloading the recognition model to %s", path)
    try:
        urllib.request.urlretrieve(url, partial)
    except (urllib.error.URLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise ModelError(
            f"Cannot download the model ({exc}). "
            f"Download it manually from {url} and save it as {path}"
        ) from exc
    partial.replace(path)
    return path


def hands(result: Any, t_ms: int) -> list[HandObservation]:
    """Le mani di un GestureRecognizerResult, una osservazione ciascuna."""
    out = []
    for categories, hand in zip(result.gestures, result.hand_landmarks):
        if not categories:
            continue
        top = categories[0]
        points = tuple((lm.x, lm.y) for lm in hand)
        gesture = None if top.category_name in ("", "None") else top.category_name
        out.append(HandObservation(gesture, top.score, points[0], t_ms, points))
    return out


class GestureRecognizer:
    """MediaPipe in modalità VIDEO, fino a due mani tracciate."""

    def __init__(self, model_path: Path) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        options = vision.GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=2,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)
        self._last_t = -1

    def recognize(self, frame_bgr: np.ndarray, t_ms: int) -> list[HandObservation]:
        # MediaPipe richiede timestamp strettamente crescenti.
        t_ms = max(t_ms, self._last_t + 1)
        self._last_t = t_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        return hands(self._recognizer.recognize_for_video(image, t_ms), t_ms)

    def close(self) -> None:
        self._recognizer.close()

    def __enter__(self) -> GestureRecognizer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
