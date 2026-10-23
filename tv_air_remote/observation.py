"""Osservazione di una mano in un singolo frame."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HandObservation:
    gesture: str | None  # nome della gesture MediaPipe, None se nessuna
    score: float
    wrist: tuple[float, float]  # coordinate normalizzate [0, 1], y verso il basso
    t_ms: int
    landmarks: tuple[tuple[float, float], ...] = ()
