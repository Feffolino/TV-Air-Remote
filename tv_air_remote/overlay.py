"""Informazioni disegnate sopra l'immagine della webcam."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import GESTURES, PALM_TRIGGERS, PLAY_PAUSE, Action
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
MODE_HINTS = {"tv": "1 mano", "nav": "2 mani"}
LINE_HEIGHT = 22
PANEL_ALPHA = 0.55
LEGEND_LINE_HEIGHT = 18
LEGEND_SCALE = 0.45
HIGHLIGHT = (0, 255, 255)  # giallo: comando della gesture riconosciuta ora
ZONE_COLOR = (200, 200, 200)

GESTURE_LABELS = {
    "PALM_UP": "Palmo su",
    "PALM_DOWN": "Palmo giu'",
    "PALM_LEFT": "Palmo a sinistra",
    "PALM_RIGHT": "Palmo a destra",
    "PALM_CLICK": "Chiudi e riapri la mano",
    "Thumb_Up": "Pollice su",
    "Thumb_Down": "Pollice giu'",
    "Victory": "Vittoria",
    "Pointing_Up": "Indice su",
    "ILoveYou": "Pollice+indice+mignolo",
    "Closed_Fist": "Pugno",
    "Open_Palm": "Palmo aperto",
    "Thumb_Left": "Pollice a sinistra",
}
KEY_LABELS = {
    PLAY_PAUSE: "pausa / play",
    "KEY_CHUP": "canale +",
    "KEY_CHDOWN": "canale -",
    "KEY_VOLUP": "volume +",
    "KEY_VOLDOWN": "volume -",
    "KEY_HOME": "Home",
    "KEY_POWER": "accendi / spegni",
    "KEY_UP": "freccia su",
    "KEY_DOWN": "freccia giu'",
    "KEY_LEFT": "freccia sinistra",
    "KEY_RIGHT": "freccia destra",
    "KEY_ENTER": "OK (pausa/play nei video)",
    "KEY_RETURN": "indietro",
    "KEY_EXIT": "esci",
}


def legend(actions: dict[str, Action], hold_ms: dict[str, int]) -> list[tuple[str, str]]:
    """Righe "gesture: comando" di una modalità, palmo per primo."""
    lines = []
    for name in (*PALM_TRIGGERS, *GESTURES):
        action = actions.get(name)
        if action is None:
            continue
        label = GESTURE_LABELS.get(name, name)
        if hold_ms.get(name):
            label += f" (tieni {hold_ms[name] / 1000:g} s)"
        lines.append((name, f"{label}: {KEY_LABELS.get(action.key, action.key)}"))
    return lines


@dataclass(frozen=True)
class JoystickView:
    """Quanto serve per disegnare il joystick del palmo."""
    center: tuple[float, float]
    zone: float
    direction: str | None  # "UP", "DOWN", "LEFT", "RIGHT" o None


def draw(
    frame: np.ndarray,
    hands: list[HandObservation],
    mode: str,
    gesture: str | None,
    last_key: str | None,
    tv_status: str,
    commands: list[tuple[str, str]] = (),
    joysticks: list[JoystickView] = (),
) -> np.ndarray:
    height, width = frame.shape[:2]
    for obs in hands:
        points = [(int(x * width), int(y * height)) for x, y in obs.landmarks]
        for a, b in HAND_CONNECTIONS:
            if a < len(points) and b < len(points):
                cv2.line(frame, points[a], points[b], (0, 255, 0), 2)
        for point in points:
            cv2.circle(frame, point, 3, (0, 0, 255), -1)
    for view in joysticks:
        _draw_joystick(frame, view)

    lines = [
        f"Modalita': {MODE_LABELS.get(mode, mode)} ({MODE_HINTS.get(mode, '')})",
        f"Gesture: {gesture or '-'}",
        f"Ultimo tasto: {last_key or '-'}",
        f"TV: {tv_status}",
    ]
    # Fondo semitrasparente: la mano alzata resta visibile sotto il testo.
    panel = frame[: LINE_HEIGHT * len(lines) + 10]
    cv2.addWeighted(panel, 1 - PANEL_ALPHA, np.zeros_like(panel), PANEL_ALPHA, 0, dst=panel)
    for i, text in enumerate(lines):
        cv2.putText(frame, text, (10, 24 + LINE_HEIGHT * i), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 1, cv2.LINE_AA)
    moving = [view.direction for view in joysticks if view.direction]
    _draw_commands(frame, commands, f"PALM_{moving[0]}" if moving else gesture)
    return frame


def _draw_joystick(frame: np.ndarray, view: JoystickView) -> None:
    """Centro e confine delle zone: oltre il riquadro parte il comando."""
    height, width = frame.shape[:2]
    cx, cy = int(view.center[0] * width), int(view.center[1] * height)
    dx, dy = int(view.zone * width), int(view.zone * height)
    cv2.rectangle(frame, (cx - dx, cy - dy), (cx + dx, cy + dy), ZONE_COLOR, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 4, ZONE_COLOR, -1)
    if view.direction is not None:
        ex, ey = {"UP": (cx, cy - dy), "DOWN": (cx, cy + dy),
                  "LEFT": (cx - dx, cy), "RIGHT": (cx + dx, cy)}[view.direction]
        cv2.arrowedLine(frame, (cx, cy), (ex, ey), HIGHLIGHT, 3, cv2.LINE_AA, tipLength=0.3)


def _draw_commands(frame: np.ndarray, commands: list[tuple[str, str]], gesture: str | None) -> None:
    """Elenco dei comandi della modalità in basso a sinistra."""
    if not commands:
        return
    height = frame.shape[0]
    top = height - LEGEND_LINE_HEIGHT * len(commands) - 8
    width = max(cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, LEGEND_SCALE, 1)[0][0]
                for _, text in commands)
    panel = frame[top:, : width + 20]
    cv2.addWeighted(panel, 1 - PANEL_ALPHA, np.zeros_like(panel), PANEL_ALPHA, 0, dst=panel)
    for i, (name, text) in enumerate(commands):
        color = HIGHLIGHT if name == gesture else (255, 255, 255)
        cv2.putText(frame, text, (10, top + 14 + LEGEND_LINE_HEIGHT * i),
                    cv2.FONT_HERSHEY_SIMPLEX, LEGEND_SCALE, color, 1, cv2.LINE_AA)
