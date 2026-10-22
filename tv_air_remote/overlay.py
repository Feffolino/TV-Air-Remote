"""Informazioni disegnate sopra l'immagine della webcam."""

from __future__ import annotations

import cv2
import numpy as np

from .observation import HandObservation

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)
# I font Hershey di OpenCV non hanno lettere accentate.
MODE_LABELS = {"tv": "TV", "nav": "Navigazione"}
LINE_HEIGHT = 22


def draw(
    frame: np.ndarray,
    obs: HandObservation | None,
    mode: str,
    gesture: str | None,
    last_key: str | None,
    tv_status: str,
) -> np.ndarray:
    height, width = frame.shape[:2]
    if obs is not None and obs.landmarks:
        points = [(int(x * width), int(y * height)) for x, y in obs.landmarks]
        for a, b in HAND_CONNECTIONS:
            if a < len(points) and b < len(points):
                cv2.line(frame, points[a], points[b], (0, 255, 0), 2)
        for point in points:
            cv2.circle(frame, point, 3, (0, 0, 255), -1)

    lines = [
        f"Modalita': {MODE_LABELS.get(mode, mode)}",
        f"Gesture: {gesture or '-'}",
        f"Ultimo tasto: {last_key or '-'}",
        f"TV: {tv_status}",
    ]
    cv2.rectangle(frame, (0, 0), (width, LINE_HEIGHT * len(lines) + 10), (0, 0, 0), -1)
    for i, text in enumerate(lines):
        cv2.putText(frame, text, (10, 24 + LINE_HEIGHT * i), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 1, cv2.LINE_AA)
    return frame
