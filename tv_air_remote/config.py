"""Caricamento e validazione della configurazione."""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any

import yaml

GESTURES = (
    "Thumb_Up",
    "Thumb_Down",
    "Victory",
    "Pointing_Up",
    "ILoveYou",
    "Closed_Fist",
    "Open_Palm",
)
SWIPES = ("SWIPE_UP", "SWIPE_DOWN", "SWIPE_LEFT", "SWIPE_RIGHT")
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
    switch_to: str | None = None


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
class Thresholds:
    min_score: float = 0.7
    stable_frames: int = 5
    cooldown_ms: int = 800
    swipe_cooldown_ms: int = 500
    repeat_ms: int = 300
    fast_repeat_ms: int = 150
    fast_after_ms: int = 1500
    hand_lost_ms: int = 300
    nav_timeout_ms: int = 8000
    swipe_arm_ms: int = 300
    swipe_still_dist: float = 0.03
    swipe_min_dist: float = 0.25
    swipe_max_ms: int = 400
    repeat_gestures: tuple[str, ...] = ("Thumb_Up", "Thumb_Down")
    hold_ms: dict[str, int] = field(
        default_factory=lambda: {"Pointing_Up": 1000, "ILoveYou": 1500}
    )


DEFAULT_MAPPING: dict[str, dict[str, Action]] = {
    "tv": {
        "SWIPE_UP": Action("KEY_CHUP"),
        "SWIPE_DOWN": Action("KEY_CHDOWN"),
        "Thumb_Up": Action("KEY_VOLUP"),
        "Thumb_Down": Action("KEY_VOLDOWN"),
        "Victory": Action(PLAY_PAUSE),
        "Pointing_Up": Action("KEY_HOME", switch_to="nav"),
        "ILoveYou": Action("KEY_POWER"),
    },
    "nav": {
        "SWIPE_UP": Action("KEY_UP"),
        "SWIPE_DOWN": Action("KEY_DOWN"),
        "SWIPE_LEFT": Action("KEY_LEFT"),
        "SWIPE_RIGHT": Action("KEY_RIGHT"),
        "Closed_Fist": Action("KEY_ENTER"),
        "Victory": Action("KEY_RETURN"),
        "Thumb_Up": Action("KEY_VOLUP"),
        "Thumb_Down": Action("KEY_VOLDOWN"),
        "Pointing_Up": Action("KEY_EXIT", switch_to="tv"),
        "ILoveYou": Action("KEY_POWER"),
    },
}


@dataclass(frozen=True)
class Config:
    tv: TvConfig
    camera: CameraConfig = field(default_factory=CameraConfig)
    thresholds: Thresholds = field(default_factory=Thresholds)
    mapping: dict[str, dict[str, Action]] = field(
        default_factory=lambda: {mode: dict(m) for mode, m in DEFAULT_MAPPING.items()}
    )


def load_config(path: str | Path) -> Config:
    """Legge e valida il file YAML di configurazione."""
    path = Path(path)
    if not path.exists():
        raise ConfigError(
            f"File di configurazione non trovato: {path}. "
            f"Copia config.example.yaml in {path} e imposta l'IP della TV."
        )
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return parse_config(data)


def parse_config(data: Any, require_host: bool = True) -> Config:
    """Valida una configurazione già letta. Le sezioni assenti usano i default."""
    if not isinstance(data, dict):
        raise ConfigError("La configurazione deve essere una mappa YAML")

    tv_data = dict(_section(data, "tv"))
    if not tv_data.get("host"):
        if require_host:
            raise ConfigError("Campo obbligatorio mancante: tv.host (indirizzo IP della TV)")
        tv_data["host"] = "dry-run"
    tv = _build(TvConfig, tv_data, "tv")
    camera = _build(CameraConfig, _section(data, "camera"), "camera")

    thr_data = dict(_section(data, "thresholds"))
    if "repeat_gestures" in thr_data:
        thr_data["repeat_gestures"] = tuple(thr_data["repeat_gestures"])
    thresholds = _build(Thresholds, thr_data, "thresholds")
    for gesture in (*thresholds.repeat_gestures, *thresholds.hold_ms):
        if gesture not in GESTURES:
            raise ConfigError(f"Gesture sconosciuta in thresholds: {gesture}")

    mapping = {mode: dict(entries) for mode, entries in DEFAULT_MAPPING.items()}
    for mode, entries in _section(data, "mapping").items():
        if mode not in MODES:
            raise ConfigError(
                f"Modalità sconosciuta in mapping: {mode} (valide: {', '.join(MODES)})"
            )
        mapping[mode] = _parse_mode(mode, entries or {})

    return Config(tv=tv, camera=camera, thresholds=thresholds, mapping=mapping)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name) or {}
    if not isinstance(value, dict):
        raise ConfigError(f"La sezione {name} deve essere una mappa")
    return value


def _build(cls: type, values: dict[str, Any], section: str) -> Any:
    unknown = set(values) - {f.name for f in fields(cls)}
    if unknown:
        raise ConfigError(f"Campo sconosciuto in {section}: {', '.join(sorted(unknown))}")
    return cls(**values)


def _parse_mode(mode: str, entries: dict[str, Any]) -> dict[str, Action]:
    actions = {}
    for trigger, value in entries.items():
        where = f"mapping.{mode}.{trigger}"
        if trigger not in GESTURES and trigger not in SWIPES:
            raise ConfigError(f"Gesture sconosciuta in mapping.{mode}: {trigger}")
        if isinstance(value, str):
            action = Action(value)
        elif isinstance(value, dict):
            action = Action(str(value.get("key", "")), value.get("switch_to"))
        else:
            raise ConfigError(f"Valore non valido in {where}: {value!r}")
        if action.key != PLAY_PAUSE and action.key not in VALID_KEYS:
            raise ConfigError(f"Tasto non valido in {where}: {action.key}")
        if action.switch_to is not None and action.switch_to not in MODES:
            raise ConfigError(f"switch_to non valido in {where}: {action.switch_to}")
        actions[trigger] = action
    return actions
