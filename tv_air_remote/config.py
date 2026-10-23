"""Caricamento e validazione della configurazione."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

from .i18n import DEFAULT_LANGUAGE, LANGUAGES

GESTURES = (
    "Thumb_Up",
    "Thumb_Down",
    "Victory",
    "Pointing_Up",
    "ILoveYou",
    "Closed_Fist",
    "Open_Palm",
    "Thumb_Left",  # pollice verso sinistra, riconosciuto dalla forma della mano
)
# Palmo aperto spostato dal centro (joystick).
PALM_MOVES = ("PALM_UP", "PALM_DOWN", "PALM_LEFT", "PALM_RIGHT")
# Palmo chiuso e riaperto in fretta.
PALM_TRIGGERS = (*PALM_MOVES, "PALM_CLICK")
MODES = ("tv", "nav")

# Azione speciale: alterna KEY_PAUSE e KEY_PLAY.
PLAY_PAUSE = "PLAY_PAUSE"

VALID_KEYS = frozenset({
    "KEY_POWER", "KEY_POWEROFF", "KEY_HOME", "KEY_MENU", "KEY_SOURCE",
    "KEY_GUIDE", "KEY_INFO", "KEY_TOOLS", "KEY_UP", "KEY_DOWN", "KEY_LEFT",
    "KEY_RIGHT", "KEY_ENTER", "KEY_RETURN", "KEY_EXIT", "KEY_CHUP",
    "KEY_CHDOWN", "KEY_PRECH", "KEY_CH_LIST", "KEY_VOLUP", "KEY_VOLDOWN",
    "KEY_MUTE", "KEY_PLAY", "KEY_PAUSE", "KEY_STOP", "KEY_FF", "KEY_REWIND",
    "KEY_RED", "KEY_GREEN", "KEY_YELLOW", "KEY_BLUE",
    *(f"KEY_{digit}" for digit in range(10)),
})


class ConfigError(ValueError):
    """Configurazione non valida."""


@dataclass(frozen=True)
class Action:
    key: str


@dataclass(frozen=True)
class TvConfig:
    host: str
    port: int = 8002
    mac: str | None = None
    token_file: str = ".tv_token"
    name: str = "TV Air Remote"


@dataclass(frozen=True)
class CameraConfig:
    index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30


@dataclass(frozen=True)
class UiConfig:
    language: str = DEFAULT_LANGUAGE


@dataclass(frozen=True)
class Thresholds:
    min_score: float = 0.7
    stable_frames: int = 5
    cooldown_ms: int = 800
    release_ms: int = 500
    click_ms: int = 700
    repeat_ms: int = 300
    fast_repeat_ms: int = 150
    fast_after_ms: int = 1500
    hand_lost_ms: int = 300
    palm_keep_ms: int = 1500
    nav_enter_ms: int = 400
    nav_exit_ms: int = 1500
    palm_arm_ms: int = 300
    palm_still_dist: float = 0.03
    palm_zone: float = 0.08
    palm_idle: float = 0.05
    palm_smoothing: float = 0.5
    palm_slow_ms: int = 700
    palm_fast_ms: int = 150
    palm_fast_dist: float = 0.20
    repeat_gestures: tuple[str, ...] = ("Thumb_Up", "Thumb_Down")
    hold_ms: dict[str, int] = field(
        default_factory=lambda: {"Closed_Fist": 1000, "ILoveYou": 1500}
    )


DEFAULT_MAPPING: dict[str, dict[str, Action]] = {
    "tv": {
        "PALM_UP": Action("KEY_VOLUP"),
        "PALM_DOWN": Action("KEY_VOLDOWN"),
        "PALM_LEFT": Action("KEY_CHDOWN"),
        "PALM_RIGHT": Action("KEY_CHUP"),
        "PALM_CLICK": Action("KEY_ENTER"),
        "Thumb_Up": Action("KEY_VOLUP"),
        "Thumb_Down": Action("KEY_VOLDOWN"),
        "Closed_Fist": Action("KEY_HOME"),
        "ILoveYou": Action("KEY_POWER"),
    },
    "nav": {
        "PALM_UP": Action("KEY_UP"),
        "PALM_DOWN": Action("KEY_DOWN"),
        "PALM_LEFT": Action("KEY_LEFT"),
        "PALM_RIGHT": Action("KEY_RIGHT"),
        "PALM_CLICK": Action("KEY_ENTER"),
        "Thumb_Up": Action("KEY_ENTER"),
        "Victory": Action("KEY_RETURN"),
        "Thumb_Left": Action("KEY_RETURN"),
        "Thumb_Down": Action("KEY_VOLDOWN"),
        "ILoveYou": Action("KEY_POWER"),
    },
}


@dataclass(frozen=True)
class Config:
    tv: TvConfig
    camera: CameraConfig = field(default_factory=CameraConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    thresholds: Thresholds = field(default_factory=Thresholds)
    mapping: dict[str, dict[str, Action]] = field(
        default_factory=lambda: {mode: dict(m) for mode, m in DEFAULT_MAPPING.items()}
    )


def load_config(path: str | Path) -> Config:
    """Legge e valida il file YAML di configurazione."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"Configuration file not found: {path}. "
            f"Copy config.example.yaml to {path} and set the TV's IP address."
        )
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return parse_config(data)


def parse_config(data: Any, require_host: bool = True) -> Config:
    """Valida una configurazione già letta. Le sezioni assenti usano i default."""
    if not isinstance(data, dict):
        raise ConfigError("The configuration must be a YAML mapping")

    tv_data = dict(_section(data, "tv"))
    if not tv_data.get("host"):
        if require_host:
            raise ConfigError("Missing required field: tv.host (IP address of the TV)")
        tv_data["host"] = "dry-run"
    tv = _build(TvConfig, tv_data, "tv")
    camera = _build(CameraConfig, _section(data, "camera"), "camera")
    ui = _build(UiConfig, _section(data, "ui"), "ui")
    if ui.language not in LANGUAGES:
        raise ConfigError(f"Unknown ui.language: {ui.language} (valid: {', '.join(LANGUAGES)})")

    thr_data = dict(_section(data, "thresholds"))
    if "repeat_gestures" in thr_data:
        thr_data["repeat_gestures"] = tuple(thr_data["repeat_gestures"])
    thresholds = _build(Thresholds, thr_data, "thresholds")
    for gesture in (*thresholds.repeat_gestures, *thresholds.hold_ms):
        if gesture not in GESTURES:
            raise ConfigError(f"Unknown gesture in thresholds: {gesture}")

    mapping = {mode: dict(entries) for mode, entries in DEFAULT_MAPPING.items()}
    for mode, entries in _section(data, "mapping").items():
        if mode not in MODES:
            raise ConfigError(
                f"Unknown mode in mapping: {mode} (valid: {', '.join(MODES)})"
            )
        mapping[mode] = _parse_mode(mode, entries or {})

    return Config(tv=tv, camera=camera, ui=ui, thresholds=thresholds, mapping=mapping)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"Section {name} must be a mapping")
    return value


def _build(cls: type, values: dict[str, Any], section: str) -> Any:
    unknown = set(values) - {f.name for f in fields(cls)}
    if unknown:
        raise ConfigError(f"Unknown field in {section}: {', '.join(sorted(unknown))}")
    return cls(**values)


def _parse_mode(mode: str, entries: dict[str, Any]) -> dict[str, Action]:
    actions = {}
    for trigger, value in entries.items():
        where = f"mapping.{mode}.{trigger}"
        if trigger not in GESTURES and trigger not in PALM_TRIGGERS:
            raise ConfigError(f"Unknown gesture in mapping.{mode}: {trigger}")
        if isinstance(value, str):
            action = Action(value)
        elif isinstance(value, dict) and set(value) == {"key"}:
            action = Action(str(value["key"]))
        else:
            raise ConfigError(f"Invalid value in {where}: {value!r}")
        if action.key != PLAY_PAUSE and action.key not in VALID_KEYS:
            raise ConfigError(f"Invalid key in {where}: {action.key}")
        actions[trigger] = action
    return actions
