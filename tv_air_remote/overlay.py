"""Information drawn on top of the webcam image."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .config import GESTURES, PALM_TRIGGERS, Action
from .i18n import DEFAULT_LANGUAGE, texts
from .observation import HandObservation

HAND_CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)
LINE_HEIGHT = 22
PANEL_ALPHA = 0.55
LEGEND_LINE_HEIGHT = 18
LEGEND_SCALE = 0.45
HIGHLIGHT = (0, 255, 255)  # yellow: command of the gesture recognised right now
ZONE_COLOR = (200, 200, 200)


def legend(
    actions: dict[str, Action], hold_ms: dict[str, int], language: str = DEFAULT_LANGUAGE
) -> list[tuple[str, str]]:
    """"Gesture: command" lines for one mode, palm moves first."""
    t = texts(language)
    lines = []
    for name in (*PALM_TRIGGERS, *GESTURES):
        action = actions.get(name)
        if action is None:
            continue
        label = t["gestures"].get(name, name)
        if hold_ms.get(name):
            label += " (" + t["hold"].format(seconds=hold_ms[name] / 1000) + ")"
        lines.append((name, f"{label}: {t['keys'].get(action.key, action.key)}"))
    return lines


@dataclass(frozen=True)
class JoystickView:
    """What is needed to draw one palm joystick."""
    center: tuple[float, float]
    zone: float
    direction: str | None  # "UP", "DOWN", "LEFT", "RIGHT" or None


def draw(
    frame: np.ndarray,
    hands: list[HandObservation],
    mode: str,
    gesture: str | None,
    last_key: str | None,
    tv_status: str,
    commands: list[tuple[str, str]] = (),
    joysticks: list[JoystickView] = (),
    language: str = DEFAULT_LANGUAGE,
) -> np.ndarray:
    t = texts(language)
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

    mode_name = t["modes"].get(mode, mode)
    hint = t["mode_hints"].get(mode, "")
    lines = [
        f"{t['mode']}: {mode_name} ({hint})" if hint else f"{t['mode']}: {mode_name}",
        f"{t['gesture']}: {t['gestures'].get(gesture, gesture) if gesture else '-'}",
        f"{t['last_key']}: {last_key or '-'}",
        f"{t['tv']}: {t['status'].get(tv_status, tv_status)}",
    ]
    # Semi-transparent background: a raised hand stays visible under the text.
    panel = frame[: LINE_HEIGHT * len(lines) + 10]
    cv2.addWeighted(panel, 1 - PANEL_ALPHA, np.zeros_like(panel), PANEL_ALPHA, 0, dst=panel)
    for i, text in enumerate(lines):
        cv2.putText(frame, text, (10, 24 + LINE_HEIGHT * i), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 1, cv2.LINE_AA)
    moving = [view.direction for view in joysticks if view.direction]
    _draw_commands(frame, commands, f"PALM_{moving[0]}" if moving else gesture)
    return frame


def _draw_joystick(frame: np.ndarray, view: JoystickView) -> None:
    """Centre and zone border: past the square a command starts."""
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
    """Commands of the current mode, bottom left."""
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
