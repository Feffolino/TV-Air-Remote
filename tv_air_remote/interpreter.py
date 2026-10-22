"""Traduzione delle osservazioni della mano in tasti della TV."""

from __future__ import annotations

from .config import PLAY_PAUSE, Action, Config
from .observation import HandObservation
from .swipe import SwipeDetector


class GestureInterpreter:
    """Macchina a stati senza I/O: riceve osservazioni, restituisce tasti.

    Il tempo arriva dall'esterno (``t_ms``), quindi il comportamento è
    deterministico e testabile.
    """

    def __init__(self, config: Config) -> None:
        self._thr = config.thresholds
        self._mapping = config.mapping
        self._swipe = SwipeDetector(
            arm_ms=self._thr.swipe_arm_ms,
            still_dist=self._thr.swipe_still_dist,
            min_dist=self._thr.swipe_min_dist,
            max_ms=self._thr.swipe_max_ms,
        )
        self.mode = "tv"
        self._paused = False
        self._ready_at = 0
        self._last_seen: int | None = None
        self._last_command = 0
        self._reset_static()

    @property
    def gesture(self) -> str | None:
        """Gesture stabile corrente, None se nessuna."""
        if self._count >= self._thr.stable_frames:
            return self._candidate
        return None

    def update(self, obs: HandObservation | None, t_ms: int) -> list[str]:
        if self.mode != "tv" and t_ms - self._last_command >= self._thr.nav_timeout_ms:
            self.mode = "tv"

        if obs is None:
            if self._last_seen is not None and t_ms - self._last_seen > self._thr.hand_lost_ms:
                self._reset_static()
                self._swipe.reset()
                self._last_seen = None
            return []

        self._last_seen = t_ms
        direction = self._swipe.update(obs.gesture, obs.wrist, t_ms)
        if direction is not None:
            return self._on_swipe(direction.value, t_ms)
        return self._on_static(obs, t_ms)

    def _on_swipe(self, name: str, t_ms: int) -> list[str]:
        self._reset_static()
        action = self._mapping[self.mode].get(f"SWIPE_{name}")
        if action is None or t_ms < self._ready_at:
            return []
        self._ready_at = t_ms + self._thr.swipe_cooldown_ms
        return [self._execute(action, t_ms)]

    def _on_static(self, obs: HandObservation, t_ms: int) -> list[str]:
        label = obs.gesture if obs.score >= self._thr.min_score else None
        if label != self._candidate:
            self._reset_static()
            self._candidate = label
            self._since = t_ms
        self._count += 1
        if label is None or self._count < self._thr.stable_frames:
            return []

        action = self._mapping[self.mode].get(label)
        if action is None:
            return []
        if label in self._thr.repeat_gestures:
            return self._repeat(action, t_ms)
        if self._fired or t_ms < self._ready_at:
            return []
        if t_ms - self._since < self._thr.hold_ms.get(label, 0):
            return []
        self._fired = True
        self._ready_at = t_ms + self._thr.cooldown_ms
        return [self._execute(action, t_ms)]

    def _repeat(self, action: Action, t_ms: int) -> list[str]:
        if self._next_repeat is None:
            if t_ms < self._ready_at:
                return []
            self._repeat_start = t_ms
        elif t_ms < self._next_repeat:
            return []
        fast = t_ms - self._repeat_start >= self._thr.fast_after_ms
        interval = self._thr.fast_repeat_ms if fast else self._thr.repeat_ms
        self._next_repeat = t_ms + interval
        return [self._execute(action, t_ms)]

    def _execute(self, action: Action, t_ms: int) -> str:
        key = action.key
        if key == PLAY_PAUSE:
            key = "KEY_PLAY" if self._paused else "KEY_PAUSE"
            self._paused = not self._paused
        if action.switch_to is not None:
            self.mode = action.switch_to
        self._last_command = t_ms
        return key

    def _reset_static(self) -> None:
        self._candidate: str | None = None
        self._count = 0
        self._since = 0
        self._fired = False
        self._next_repeat: int | None = None
        self._repeat_start = 0
