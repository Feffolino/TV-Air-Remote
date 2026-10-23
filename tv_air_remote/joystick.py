"""Palmo aperto usato come joystick: centro a riposo e quattro direzioni."""

from __future__ import annotations

import math
from enum import Enum

OPEN_PALM = "Open_Palm"
# (punta, nocca intermedia) di indice, medio, anulare e mignolo.
FINGERS = ((8, 6), (12, 10), (16, 14), (20, 18))
# Polso e attaccature delle dita: la loro media è il centro del palmo.
PALM_POINTS = (0, 5, 9, 13, 17)


def is_open_hand(landmarks: tuple[tuple[float, float], ...]) -> bool:
    """Quattro dita distese: ogni punta più lontana dal polso della sua nocca.

    Serve quando MediaPipe classifica come "nessuna gesture" un palmo aperto.
    """
    if len(landmarks) < 21:
        return False
    wx, wy = landmarks[0]

    def dist(i: int) -> float:
        return math.hypot(landmarks[i][0] - wx, landmarks[i][1] - wy)

    return all(dist(tip) > 1.1 * dist(pip) for tip, pip in FINGERS)


def is_thumb_left(landmarks: tuple[tuple[float, float], ...]) -> bool:
    """Dita piegate e pollice disteso verso sinistra nell'immagine.

    MediaPipe non ha questa gesture (e spesso la scambia per un pugno): la si
    riconosce dalla forma. L'immagine è specchiata, quindi sinistra a schermo
    è la sinistra di chi guarda la TV.
    """
    if len(landmarks) < 21:
        return False
    wx, wy = landmarks[0]

    def dist(i: int, j: int = 0) -> float:
        return math.hypot(landmarks[i][0] - landmarks[j][0], landmarks[i][1] - landmarks[j][1])

    if not all(dist(tip) < dist(pip) for tip, pip in FINGERS):
        return False  # le quattro dita devono essere piegate
    dx = landmarks[4][0] - landmarks[2][0]
    dy = landmarks[4][1] - landmarks[2][1]
    if dist(4, 2) < 0.5 * dist(9):
        return False  # pollice non disteso
    if dx >= 0 or abs(dx) < 1.5 * abs(dy):
        return False  # non punta a sinistra
    return landmarks[4][0] < min(landmarks[i][0] for i in range(5, 21))


def palm_point(landmarks: tuple[tuple[float, float], ...], wrist: tuple[float, float]) -> tuple[float, float]:
    """Centro del palmo: segue la mano meglio del polso, che si muove poco."""
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
    """Il palmo aperto si comporta come una levetta.

    La posizione viene mediata (``smoothing``: peso del frame nuovo) per
    togliere il tremolio. Il centro si fissa dove il palmo resta fermo (entro
    ``still_dist``) per ``arm_ms``. Spostandolo oltre ``zone`` dal centro si
    entra in una direzione: il comando parte subito e si ripete finché la mano
    resta lì, tanto più in fretta quanto più è lontana dal centro (da
    ``slow_ms`` sul confine a ``fast_ms`` oltre ``fast_dist``). Rientrando
    entro ``idle`` dal centro si torna a riposo; passando in un'altra direzione
    il comando cambia subito. Tra ``idle`` e ``zone`` lo stato non cambia, così
    il tremolio sul confine non fa scattare comandi. Le direzioni fuori da
    ``allowed`` valgono come riposo. In diagonale l'asse in corso resta finché
    l'altro non è più grande di ``axis_bias`` volte, così la direzione non
    salta tra i due assi. Dopo ``latch`` il joystick tace finché il palmo non
    torna al centro, che resta quello di prima; con ``recenter`` anche un palmo
    fermo altrove per ``arm_ms`` sposta lì il centro.
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
        """Distanza del palmo dal centro nell'ultimo aggiornamento."""
        return self._offset

    @property
    def entered_t(self) -> int:
        """Istante in cui è iniziata la direzione corrente."""
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
        """Niente comandi finché il palmo non rientra al centro.

        ``recenter``: per una mano ricomparsa, che può tornare in un punto
        diverso; fermandosi lì per ``arm_ms`` il centro si sposta.
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
        """Nuova posizione del palmo aperto. Restituisce la direzione da inviare."""
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
            # Fermo lontano dal centro di prima: quello diventa il nuovo centro.
            if self._still is None or math.hypot(x - self._still[1], y - self._still[2]) > self.still_dist:
                self._still = (t_ms, x, y)
            elif t_ms - self._still[0] >= self.arm_ms:
                self._center = (self._still[1], self._still[2])
                self._latched = False
                self._offset = 0.0
            return None
        if offset < self.zone:
            # Tra idle e zone la direzione resta memorizzata ma non si ripete:
            # una mano rimasta appena spostata non deve continuare a inviare.
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
        """Intervallo di ripetizione: lento sul confine, veloce lontano dal centro."""
        span = self.fast_dist - self.zone
        k = min(max((offset - self.zone) / span, 0.0), 1.0) if span > 0 else 1.0
        return self.slow_ms - (self.slow_ms - self.fast_ms) * k
