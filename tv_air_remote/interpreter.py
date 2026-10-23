"""Translation of hand observations into TV keys."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from .config import PLAY_PAUSE, Action, Config
from .joystick import (ALL_DIRECTIONS, OPEN_PALM, VERTICAL, Direction, PalmJoystick, is_open_hand,
                       is_thumb_left, palm_point)
from .observation import HandObservation

CLOSED_FIST = "Closed_Fist"
THUMB_LEFT = "Thumb_Left"  # recognised from the shape, MediaPipe does not know it
# Palm → fist → palm in quick succession: a "click".
CLICK = "PALM_CLICK"
# Minimum fist frames for a click: a single one may be a MediaPipe error.
CLICK_MIN_FRAMES = 2

# Only volume repeats while the gesture is held: a thumbs-up mapped to OK does not.
REPEAT_KEYS = frozenset({"KEY_VOLUP", "KEY_VOLDOWN"})
# With two hands in Navigation mode, each one only pushes towards its own side.
SIDE_DIRECTIONS = {
    "left": frozenset({Direction.LEFT, Direction.UP, Direction.DOWN}),
    "right": frozenset({Direction.RIGHT, Direction.UP, Direction.DOWN}),
}


@dataclass
class _Slot:
    """A hand tracked over time, with its joystick."""
    joystick: PalmJoystick
    point: tuple[float, float] | None = None
    seen: int | None = None
    palm_seen: int | None = None
    fist_since: int | None = None  # fist just closed after the palm: maybe a click
    fist_frames: int = 0

    def reset(self) -> None:
        self.joystick.reset()
        self.point = self.seen = self.palm_seen = self.fist_since = None
        self.fist_frames = 0


class GestureInterpreter:
    """State machine without I/O: takes the hands of one frame, returns keys.

    The mode depends on how many hands are in view: two hands for
    ``nav_enter_ms`` = Navigation, a single hand for ``nav_exit_ms`` = TV.
    Leaving is slower because MediaPipe often loses one of the two hands for
    a few hundred ms.

    Each hand with an open palm acts as a joystick. With two hands in
    Navigation mode, the leftmost hand in the image does left, up and down, the
    rightmost does right, up and down; up and down come from one hand at a time.
    With a single hand, that hand does all directions. Closing and reopening
    the palm within ``click_ms`` is a click (``PALM_CLICK``) and does not move
    the centre. The other gestures are commands, taken from the most confident
    hand.

    Time comes from outside (``t_ms``), so the behaviour is deterministic
    and testable.
    """

    def __init__(self, config: Config) -> None:
        self._thr = config.thresholds
        self._mapping = config.mapping
        self._slots = {side: _Slot(self._new_joystick()) for side in ("left", "right")}
        self.mode = "tv"
        self._pending_mode: str | None = None
        self._pending_since = 0
        self._paused = False
        self._ready_at = 0
        self._last_seen: int | None = None
        self._fired_label: str | None = None
        self._fired_seen = 0
        self.last_source: str | None = None  # hand ("left"/"right") of the last command
        self._reset_static()

    def _new_joystick(self) -> PalmJoystick:
        return PalmJoystick(
            arm_ms=self._thr.palm_arm_ms,
            still_dist=self._thr.palm_still_dist,
            zone=self._thr.palm_zone,
            idle=self._thr.palm_idle,
            smoothing=self._thr.palm_smoothing,
            slow_ms=self._thr.palm_slow_ms,
            fast_ms=self._thr.palm_fast_ms,
            fast_dist=self._thr.palm_fast_dist,
        )

    @property
    def joysticks(self) -> dict[str, PalmJoystick]:
        return {side: slot.joystick for side, slot in self._slots.items()}

    @property
    def gesture(self) -> str | None:
        """Current stable gesture, None if there is none."""
        if any(slot.palm_seen is not None for slot in self._slots.values()):
            return OPEN_PALM
        if self._count >= self._thr.stable_frames:
            return self._candidate
        return None

    def update(self, hands: list[HandObservation], t_ms: int) -> list[str]:
        self._update_mode(len(hands), t_ms)
        assigned = self._assign(hands)
        # A hand lost briefly keeps its centre: MediaPipe often loses one of
        # the two hands, and recentring every time would leave it silent.
        for side, slot in self._slots.items():
            if side not in assigned and slot.seen is not None \
                    and t_ms - slot.seen > self._thr.palm_keep_ms:
                slot.reset()
        if not hands:
            if self._last_seen is not None and t_ms - self._last_seen > self._thr.hand_lost_ms:
                self._reset_static()
                self._last_seen = None
            return []
        self._last_seen = t_ms

        split = self.mode == "nav" and len(assigned) == 2
        clicked = False
        moves: list[tuple[str, Direction]] = []
        statics: list[HandObservation] = []
        for side, obs in assigned.items():
            if is_thumb_left(obs.landmarks):
                obs = replace(obs, gesture=THUMB_LEFT, score=1.0)
            slot = self._slots[side]
            if slot.seen is not None and t_ms - slot.seen > self._thr.hand_lost_ms:
                # Reappeared: no commands until it returns to the centre or
                # stays still where it is.
                slot.joystick.latch(recenter=True)
                slot.palm_seen = slot.fist_since = None
                slot.fist_frames = 0
            slot.point = palm_point(obs.landmarks, obs.wrist)
            slot.seen = t_ms
            if self._is_palm(obs):
                if slot.fist_since is not None:
                    if slot.fist_frames >= CLICK_MIN_FRAMES and t_ms - slot.fist_since <= self._thr.click_ms:
                        clicked = True
                    slot.fist_since, slot.fist_frames = None, 0
                slot.palm_seen = t_ms
                allowed = SIDE_DIRECTIONS[side] if split else ALL_DIRECTIONS
                direction = slot.joystick.update(slot.point, t_ms, allowed)
                if direction is not None:
                    moves.append((side, direction))
            elif obs.gesture == CLOSED_FIST and slot.palm_seen is not None \
                    and t_ms - (slot.fist_since or t_ms) <= self._thr.click_ms:
                # Maybe a click: the joystick centre stays, but the fist still
                # counts as a gesture (held for long, it opens Home).
                if slot.fist_since is None:
                    slot.fist_since = t_ms
                slot.fist_frames += 1
                statics.append(obs)
            elif slot.palm_seen is not None and t_ms - slot.palm_seen <= self._thr.hand_lost_ms \
                    and slot.fist_since is None:
                pass  # MediaPipe loses the palm label for a few frames: wait.
            else:
                slot.palm_seen = slot.fist_since = None
                slot.fist_frames = 0
                slot.joystick.reset()
                statics.append(obs)

        keys: list[str] = []
        if clicked:
            self._reset_static()  # the click's fist must not become a command
            action = self._mapping[self.mode].get(CLICK)
            if action is not None:
                keys += self._execute(action)
                self.last_source = None
        for side, direction in moves:
            if direction in VERTICAL and not self._owns_vertical(side):
                continue
            action = self._mapping[self.mode].get(f"PALM_{direction.value}")
            if action is not None:
                keys += self._execute(action)
                self.last_source = side
        if statics:
            static_keys = self._on_static(max(statics, key=lambda h: h.score), t_ms)
            if static_keys:
                self.last_source = None
            keys += static_keys
        else:
            self._reset_static()
        return keys

    def _assign(self, hands: list[HandObservation]) -> dict[str, HandObservation]:
        """Hands → slots: by position with two hands, the nearest slot with one."""
        if len(hands) >= 2:
            left, right = sorted(hands[:2], key=lambda h: palm_point(h.landmarks, h.wrist)[0])
            return {"left": left, "right": right}
        if not hands:
            return {}
        hand = hands[0]
        px, py = palm_point(hand.landmarks, hand.wrist)
        known = [(side, s) for side, s in self._slots.items() if s.point is not None]
        if not known:
            return {"right": hand}
        side = min(known, key=lambda item: math.hypot(item[1].point[0] - px, item[1].point[1] - py))[0]
        return {side: hand}

    def _owns_vertical(self, side: str) -> bool:
        """Up and down from one hand only: the one that started them first."""
        mine = self._slots[side].joystick
        other = self._slots["right" if side == "left" else "left"].joystick
        # The other hand keeps up/down only if it is really past the threshold,
        # not if it was left slightly off centre after a command.
        if other.direction not in VERTICAL or other.offset < other.zone:
            return True
        return (mine.entered_t, side != "left") < (other.entered_t, side == "left")

    def _update_mode(self, count: int, t_ms: int) -> None:
        if count == 0:
            self._pending_mode = None
            return
        target = "nav" if count >= 2 else "tv"
        if target == self.mode:
            self._pending_mode = None
        elif target != self._pending_mode:
            self._pending_mode = target
            self._pending_since = t_ms
        else:
            wait = self._thr.nav_enter_ms if target == "nav" else self._thr.nav_exit_ms
            if t_ms - self._pending_since >= wait:
                self.mode = target
                self._pending_mode = None
                # No commands carried over from the other mode: the palm must
                # first return to the centre, which stays where it was.
                for slot in self._slots.values():
                    slot.joystick.latch()
                self._reset_static()

    @staticmethod
    def _is_palm(obs: HandObservation) -> bool:
        if obs.gesture == OPEN_PALM:
            return True
        return obs.gesture is None and is_open_hand(obs.landmarks)

    def _on_static(self, obs: HandObservation, t_ms: int) -> list[str]:
        label = obs.gesture if obs.score >= self._thr.min_score else None
        # A gesture already executed holds until it is released for release_ms:
        # a label lost for a moment does not trigger it again.
        if label is not None and label == self._fired_label:
            if t_ms - self._fired_seen <= self._thr.release_ms:
                self._fired_seen = t_ms
                return []
            self._fired_label = None
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
        if label in self._thr.repeat_gestures and action.key in REPEAT_KEYS:
            return self._repeat(action, t_ms)
        if t_ms < self._ready_at:
            return []
        if t_ms - self._since < self._thr.hold_ms.get(label, 0):
            return []
        self._fired_label = label
        self._fired_seen = t_ms
        self._ready_at = t_ms + self._thr.cooldown_ms
        return self._execute(action)

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
        return self._execute(action)

    def _execute(self, action: Action) -> list[str]:
        key = action.key
        if key == PLAY_PAUSE:
            key = "KEY_PLAY" if self._paused else "KEY_PAUSE"
            self._paused = not self._paused
        return [key]

    def _reset_static(self) -> None:
        self._candidate: str | None = None
        self._count = 0
        self._since = 0
        self._next_repeat: int | None = None
        self._repeat_start = 0
