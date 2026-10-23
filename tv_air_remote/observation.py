"""Observation of one hand in a single frame."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandObservation:
    gesture: str | None  # MediaPipe gesture name, None if there is none
    score: float
    wrist: tuple[float, float]  # normalised coordinates [0, 1], y pointing down
    t_ms: int
    landmarks: tuple[tuple[float, float], ...] = ()
