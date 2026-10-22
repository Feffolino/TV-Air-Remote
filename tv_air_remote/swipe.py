"""Rilevamento degli swipe dal movimento del polso."""

from __future__ import annotations

import math
from enum import Enum

OPEN_PALM = "Open_Palm"


class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


class SwipeDetector:
    """Rileva uno swipe che parte da un palmo aperto e fermo.

    Lo swipe si arma quando il palmo resta entro ``still_dist`` dal punto di
    partenza per almeno ``arm_ms``. Da armato, uno spostamento di almeno
    ``min_dist`` entro ``max_ms`` dall'ultimo istante da fermo produce una
    direzione. Durante il movimento l'etichetta della gesture non conta: il
    mosso confonde il classificatore.
    """

    def __init__(
        self,
        arm_ms: int = 300,
        still_dist: float = 0.03,
        min_dist: float = 0.25,
        max_ms: int = 400,
    ) -> None:
        self.arm_ms = arm_ms
        self.still_dist = still_dist
        self.min_dist = min_dist
        self.max_ms = max_ms
        self.reset()

    @property
    def armed(self) -> bool:
        return self._armed

    def reset(self) -> None:
        self._anchor: tuple[int, float, float] | None = None
        self._last_still: tuple[int, float, float] | None = None
        self._armed = False

    def update(
        self, gesture: str | None, wrist: tuple[float, float], t_ms: int
    ) -> Direction | None:
        x, y = wrist
        if self._anchor is None:
            self._start(gesture, x, y, t_ms)
            return None

        anchor_t, anchor_x, anchor_y = self._anchor
        if math.hypot(x - anchor_x, y - anchor_y) <= self.still_dist:
            if gesture != OPEN_PALM:
                self.reset()
                return None
            self._last_still = (t_ms, x, y)
            if t_ms - anchor_t >= self.arm_ms:
                self._armed = True
            return None

        if not self._armed:
            self.reset()
            self._start(gesture, x, y, t_ms)
            return None

        still_t, still_x, still_y = self._last_still
        if t_ms - still_t > self.max_ms:
            self.reset()
            self._start(gesture, x, y, t_ms)
            return None

        dx, dy = x - still_x, y - still_y
        if max(abs(dx), abs(dy)) < self.min_dist:
            return None

        self.reset()
        if abs(dx) >= abs(dy):
            return Direction.RIGHT if dx > 0 else Direction.LEFT
        return Direction.DOWN if dy > 0 else Direction.UP

    def _start(self, gesture: str | None, x: float, y: float, t_ms: int) -> None:
        if gesture == OPEN_PALM:
            self._anchor = self._last_still = (t_ms, x, y)
