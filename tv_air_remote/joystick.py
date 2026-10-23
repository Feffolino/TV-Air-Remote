"""Open palm used as a joystick: a rest centre and four directions."""

from __future__ import annotations

import math
from enum import Enum

OPEN_PALM = "Open_Palm"
# (tip, middle knuckle) of the index, middle, ring and little fingers.
FINGERS = ((8, 6), (12, 10), (16, 14), (20, 18))
# Wrist and finger bases: their average is the centre of the palm.
PALM_POINTS = (0, 5, 9, 13, 17)


def is_open_hand(landmarks: tuple[tuple[float, float], ...]) -> bool:
    """Four fingers extended: each tip farther from the wrist than its knuckle.

    Needed when MediaPipe classifies an open palm as "no gesture".
    """
    if len(landmarks) < 21:
        return False
    wx, wy = landmarks[0]

    def dist(i: int) -> float:
        return math.hypot(landmarks[i][0] - wx, landmarks[i][1] - wy)

    return all(dist(tip) > 1.1 * dist(pip) for tip, pip in FINGERS)


def is_thumb_left(landmarks: tuple[tuple[float, float], ...]) -> bool:
    """Fingers bent and thumb extended towards the left of the image.

    MediaPipe does not have this gesture (and often mistakes it for a fist), so
    it is recognised from the shape. The image is mirrored, so left on screen
    is the left of the person watching the TV.
    """
    if len(landmarks) < 21:
        return False
    wx, wy = landmarks[0]

    def dist(i: int, j: int = 0) -> float:
        return math.hypot(landmarks[i][0] - landmarks[j][0], landmarks[i][1] - landmarks[j][1])

    if not all(dist(tip) < dist(pip) for tip, pip in FINGERS):
        return False  # the four fingers must be bent
    dx = landmarks[4][0] - landmarks[2][0]
    dy = landmarks[4][1] - landmarks[2][1]
    if dist(4, 2) < 0.5 * dist(9):
        return False  # thumb not extended
    if dx >= 0 or abs(dx) < 1.5 * abs(dy):
        return False  # not pointing left
    return landmarks[4][0] < min(landmarks[i][0] for i in range(5, 21))


def palm_point(landmarks: tuple[tuple[float, float], ...], wrist: tuple[float, float]) -> tuple[float, float]:
    """Centre of the palm: follows the hand better than the wrist, which moves little."""
    if len(landmarks) < 21:
        return wrist
    xs = [landmarks[i][0] for i in PALM_POINTS]
    ys = [landmarks[i][1] for i in PALM_POINTS]
    return sum(xs) / len(xs), sum(ys) / len(ys)


class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    LEFT = "LEFT"
    RIGHT = "RIGHT"


ALL_DIRECTIONS = frozenset(Direction)
HORIZONTAL = frozenset({Direction.LEFT, Direction.RIGHT})
VERTICAL = frozenset({Direction.UP, Direction.DOWN})


class PalmJoystick:
    """The open palm behaves like a joystick stick.

    The position is averaged (``smoothing``: weight of the new frame) to
    remove jitter. The centre is fixed where the palm stays still (within
    ``still_dist``) for ``arm_ms``. Moving it beyond ``zone`` from the centre
    enters a direction: the command fires at once and repeats while the hand
    stays there, faster the farther it is from the centre (from ``slow_ms``
    at the boundary to ``fast_ms`` beyond ``fast_dist``). Coming back within
    ``idle`` of the centre returns to rest; moving into another direction
    changes the command at once. Between ``idle`` and ``zone`` the state does
    not change, so jitter on the boundary does not trigger commands.
    Directions outside ``allowed`` count as rest. On a diagonal the current
    axis is kept until the other one is more than ``axis_bias`` times larger,
    so the direction does not jump between the two axes. After ``latch`` the
    joystick stays silent until the palm returns to the centre, which stays
    the previous one; with ``recenter`` a palm held still elsewhere for
    ``arm_ms`` also moves the centre there.
    """

    def __init__(
        self,
        arm_ms: int = 300,
        still_dist: float = 0.03,
        zone: float = 0.08,
        idle: float = 0.05,
        smoothing: float = 0.5,
        slow_ms: int = 700,
        fast_ms: int = 150,
        fast_dist: float = 0.20,
        axis_bias: float = 1.5,
    ) -> None:
        self.arm_ms = arm_ms
        self.still_dist = still_dist
        self.zone = zone
        self.idle = idle
        self.smoothing = smoothing
        self.slow_ms = slow_ms
        self.fast_ms = fast_ms
        self.fast_dist = fast_dist
        self.axis_bias = axis_bias
        self.reset()

    @property
    def center(self) -> tuple[float, float] | None:
        return self._center

    @property
    def direction(self) -> Direction | None:
        return self._direction

    @property
    def offset(self) -> float:
        """Distance of the palm from the centre at the last update."""
        return self._offset

    @property
    def entered_t(self) -> int:
        """Time at which the current direction started."""
        return self._entered_t

    def reset(self) -> None:
        self._pos: tuple[float, float] | None = None
        self._center: tuple[float, float] | None = None
        self._still: tuple[int, float, float] | None = None
        self._direction: Direction | None = None
        self._entered_t = 0
        self._last_fire = 0
        self._latched = False
        self._recenter = False
        self._offset = 0.0

    def latch(self, recenter: bool = False) -> None:
        """No commands until the palm returns to the centre.

        ``recenter``: for a hand that reappeared, which may come back at a
        different point; if it stays still there for ``arm_ms`` the centre moves.
        """
        self._latched = True
        self._recenter = recenter
        self._direction = None
        self._still = None

    def update(
        self,
        point: tuple[float, float],
        t_ms: int,
        allowed: frozenset[Direction] = ALL_DIRECTIONS,
    ) -> Direction | None:
        """New position of the open palm. Returns the direction to send."""
        if self._pos is None:
            self._pos = point
        else:
            a = self.smoothing
            self._pos = (a * point[0] + (1 - a) * self._pos[0],
                         a * point[1] + (1 - a) * self._pos[1])
        x, y = self._pos
        if self._center is None:
            if self._still is None or math.hypot(x - self._still[1], y - self._still[2]) > self.still_dist:
                self._still = (t_ms, x, y)
            elif t_ms - self._still[0] >= self.arm_ms:
                self._center = (self._still[1], self._still[2])
            return None

        dx, dy = x - self._center[0], y - self._center[1]
        offset = self._offset = max(abs(dx), abs(dy))
        if offset < self.idle:
            self._direction = None
            self._latched = False
            return None
        if self._latched:
            if not self._recenter:
                return None
            # Still, away from the previous centre: this becomes the new centre.
            if self._still is None or math.hypot(x - self._still[1], y - self._still[2]) > self.still_dist:
                self._still = (t_ms, x, y)
            elif t_ms - self._still[0] >= self.arm_ms:
                self._center = (self._still[1], self._still[2])
                self._latched = False
                self._offset = 0.0
            return None
        if offset < self.zone:
            # Between idle and zone the direction is remembered but not repeated:
            # a hand left slightly off centre must not keep sending.
            return None
        elif self._direction in HORIZONTAL and abs(dx) * self.axis_bias >= abs(dy):
            direction = Direction.RIGHT if dx > 0 else Direction.LEFT
        elif self._direction in VERTICAL and abs(dy) * self.axis_bias >= abs(dx):
            direction = Direction.DOWN if dy > 0 else Direction.UP
        elif abs(dx) >= abs(dy):
            direction = Direction.RIGHT if dx > 0 else Direction.LEFT
        else:
            direction = Direction.DOWN if dy > 0 else Direction.UP
        if direction not in allowed:
            self._direction = None
            return None
        if direction is not self._direction:
            self._direction = direction
            self._entered_t = self._last_fire = t_ms
            return direction
        if t_ms - self._last_fire >= self._interval(offset):
            self._last_fire = t_ms
            return direction
        return None

    def _interval(self, offset: float) -> float:
        """Repeat interval: slow at the boundary, fast far from the centre."""
        span = self.fast_dist - self.zone
        k = min(max((offset - self.zone) / span, 0.0), 1.0) if span > 0 else 1.0
        return self.slow_ms - (self.slow_ms - self.fast_ms) * k
