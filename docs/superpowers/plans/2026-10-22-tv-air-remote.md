# TV Air Remote Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Controllare una Smart TV Samsung Tizen con gesture delle mani riprese da webcam e riconosciute in tempo reale (spec: `docs/superpowers/specs/2026-10-22-tv-air-remote-design.md`).

**Architecture:** Un solo processo Python. Thread principale: webcam → MediaPipe GestureRecognizer → `GestureInterpreter` (macchina a stati pura, testabile) → `TvController.send()`. Il `TvController` invia i tasti in un thread separato tramite coda, con riconnessione e Wake-on-LAN. Overlay OpenCV per il feedback.

**Tech Stack:** Python 3.12, mediapipe 1.1 (Tasks API), opencv-contrib-python (dipendenza di mediapipe), samsungtvws 3.x, wakeonlan, pyyaml, pytest.

**Note di ambiente verificate:**
- `samsungtvws.SamsungTVWS` ha `key_press_delay=1` di default (dorme 1 s dopo ogni tasto): va passato `key_press_delay=0`.
- Eccezioni: `samsungtvws.exceptions.UnauthorizedError` (sottoclasse di `ConnectionFailure`); errori di rete arrivano come `OSError`/`websocket` exceptions.
- MediaPipe: `vision.GestureRecognizer.create_from_options(...)`, `recognize_for_video(mp.Image, t_ms)` con timestamp strettamente crescenti; il recognizer va chiuso esplicitamente (`close()`), altrimenti errore allo spegnimento dell'interprete.
- Modello: `https://storage.googleapis.com/mediapipe-models/gesture_recognizer/gesture_recognizer/float16/latest/gesture_recognizer.task` (circa 8 MB).
- Non installare `opencv-python` insieme a `opencv-contrib-python`: entrambi forniscono `cv2` e si rompono a vicenda.

---

## File Structure

| File | Responsabilità |
|---|---|
| `pyproject.toml` | metadati, dipendenze, config pytest |
| `.gitignore` | venv, cache, modello, config locale, token |
| `tv_air_remote/__init__.py` | versione |
| `tv_air_remote/config.py` | dataclass di configurazione, default, validazione YAML |
| `tv_air_remote/observation.py` | `HandObservation` (dato condiviso, nessuna dipendenza) |
| `tv_air_remote/swipe.py` | `SwipeDetector`, `Direction` |
| `tv_air_remote/interpreter.py` | `GestureInterpreter`: osservazioni → tasti |
| `tv_air_remote/tv.py` | `TvController`, `TvStatus`, `DryRunTv` |
| `tv_air_remote/recognizer.py` | download modello, `best_hand`, `GestureRecognizer` |
| `tv_air_remote/camera.py` | `Camera`, `CameraError` |
| `tv_air_remote/overlay.py` | `draw()` |
| `tv_air_remote/__main__.py` | CLI e ciclo principale |
| `config.example.yaml` | esempio commentato |
| `README.md` | installazione, uso, gesture, checklist manuale |
| `tests/test_*.py` | un file di test per modulo |

---

### Task 1: Scaffold del progetto

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `tv_air_remote/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Crea `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "tv-air-remote"
version = "0.1.0"
description = "Controllo di una Smart TV Samsung con le gesture delle mani"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "mediapipe>=0.10.14",
    "opencv-contrib-python>=4.9",
    "samsungtvws>=2.6",
    "wakeonlan>=3.0",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools]
packages = ["tv_air_remote"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Crea `.gitignore`**

```gitignore
.venv/
__pycache__/
*.egg-info/
.pytest_cache/
models/
config.yaml
.tv_token
```

- [ ] **Step 3: Crea `tv_air_remote/__init__.py` e `tests/__init__.py`**

`tv_air_remote/__init__.py`:
```python
"""TV Air Remote: controllo di una Smart TV Samsung con le gesture delle mani."""

__version__ = "0.1.0"
```

`tests/__init__.py`: file vuoto.

- [ ] **Step 4: Installa in modalità sviluppo e verifica pytest**

Run: `python3.12 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/pytest -q`
Expected: `no tests ran`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore tv_air_remote/__init__.py tests/__init__.py
git commit -m "Scaffold Python package"
```

---

### Task 2: Configurazione

**Files:**
- Create: `tv_air_remote/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Scrivi i test**

```python
import pytest

from tv_air_remote.config import (
    Action,
    ConfigError,
    load_config,
    parse_config,
)


def write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_minimal_config_uses_defaults(tmp_path):
    cfg = load_config(write(tmp_path, "tv:\n  host: 192.168.1.50\n"))
    assert cfg.tv.host == "192.168.1.50"
    assert cfg.tv.port == 8002
    assert cfg.tv.mac is None
    assert cfg.camera.index == 0
    assert cfg.thresholds.stable_frames == 5
    assert cfg.thresholds.hold_ms == {"Pointing_Up": 1000, "ILoveYou": 1500}
    assert cfg.mapping["tv"]["SWIPE_UP"] == Action("KEY_CHUP")
    assert cfg.mapping["tv"]["Pointing_Up"] == Action("KEY_HOME", switch_to="nav")
    assert cfg.mapping["nav"]["Closed_Fist"] == Action("KEY_ENTER")


def test_missing_file(tmp_path):
    with pytest.raises(ConfigError, match="config.example.yaml"):
        load_config(tmp_path / "missing.yaml")


def test_missing_host(tmp_path):
    with pytest.raises(ConfigError, match="tv.host"):
        load_config(write(tmp_path, "camera:\n  index: 1\n"))


def test_host_not_required_for_dry_run():
    cfg = parse_config({}, require_host=False)
    assert cfg.tv.host == "dry-run"


def test_unknown_field(tmp_path):
    with pytest.raises(ConfigError, match="prot"):
        load_config(write(tmp_path, "tv:\n  host: 1.2.3.4\n  prot: 8002\n"))


def test_thresholds_override(tmp_path):
    cfg = load_config(write(
        tmp_path,
        "tv:\n  host: 1.2.3.4\n"
        "thresholds:\n  stable_frames: 3\n  repeat_gestures: [Thumb_Up]\n",
    ))
    assert cfg.thresholds.stable_frames == 3
    assert cfg.thresholds.repeat_gestures == ("Thumb_Up",)
    assert cfg.thresholds.cooldown_ms == 800


def test_unknown_gesture_in_thresholds(tmp_path):
    with pytest.raises(ConfigError, match="Thumbs_Up"):
        load_config(write(
            tmp_path,
            "tv:\n  host: 1.2.3.4\nthresholds:\n  repeat_gestures: [Thumbs_Up]\n",
        ))


def test_mapping_override_replaces_only_that_mode(tmp_path):
    cfg = load_config(write(
        tmp_path,
        "tv:\n  host: 1.2.3.4\n"
        "mapping:\n  tv:\n    Closed_Fist: KEY_MUTE\n"
        "    Pointing_Up: {key: KEY_HOME, switch_to: nav}\n",
    ))
    assert cfg.mapping["tv"] == {
        "Closed_Fist": Action("KEY_MUTE"),
        "Pointing_Up": Action("KEY_HOME", switch_to="nav"),
    }
    assert cfg.mapping["nav"]["Closed_Fist"] == Action("KEY_ENTER")


def test_invalid_key(tmp_path):
    with pytest.raises(ConfigError, match="KEY_VOLUMEUP"):
        load_config(write(
            tmp_path, "tv:\n  host: 1.2.3.4\nmapping:\n  tv:\n    Thumb_Up: KEY_VOLUMEUP\n"
        ))


def test_unknown_gesture_in_mapping(tmp_path):
    with pytest.raises(ConfigError, match="Thumbs_Up"):
        load_config(write(
            tmp_path, "tv:\n  host: 1.2.3.4\nmapping:\n  tv:\n    Thumbs_Up: KEY_VOLUP\n"
        ))


def test_unknown_mode(tmp_path):
    with pytest.raises(ConfigError, match="menu"):
        load_config(write(
            tmp_path, "tv:\n  host: 1.2.3.4\nmapping:\n  menu:\n    Thumb_Up: KEY_VOLUP\n"
        ))


def test_invalid_switch_to(tmp_path):
    with pytest.raises(ConfigError, match="switch_to"):
        load_config(write(
            tmp_path,
            "tv:\n  host: 1.2.3.4\nmapping:\n  tv:\n"
            "    Pointing_Up: {key: KEY_HOME, switch_to: menu}\n",
        ))


def test_play_pause_is_valid_action(tmp_path):
    cfg = load_config(write(
        tmp_path, "tv:\n  host: 1.2.3.4\nmapping:\n  nav:\n    Victory: PLAY_PAUSE\n"
    ))
    assert cfg.mapping["nav"]["Victory"] == Action("PLAY_PAUSE")
```

- [ ] **Step 2: Verifica che falliscano**

Run: `.venv/bin/pytest tests/test_config.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tv_air_remote.config'`

- [ ] **Step 3: Implementa `tv_air_remote/config.py`**

```python
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
```

- [ ] **Step 4: Verifica che passino**

Run: `.venv/bin/pytest tests/test_config.py -q`
Expected: `13 passed`

- [ ] **Step 5: Commit**

```bash
git add tv_air_remote/config.py tests/test_config.py
git commit -m "Add configuration loading and validation"
```

---

### Task 3: Osservazione e rilevamento swipe

**Files:**
- Create: `tv_air_remote/observation.py`, `tv_air_remote/swipe.py`
- Test: `tests/test_swipe.py`

- [ ] **Step 1: Scrivi i test**

```python
import pytest

from tv_air_remote.swipe import Direction, SwipeDetector


def feed(detector, frames):
    """frames: (t_ms, gesture, x, y). Restituisce [(t_ms, Direction)]."""
    out = []
    for t, gesture, x, y in frames:
        result = detector.update(gesture, (x, y), t)
        if result is not None:
            out.append((t, result))
    return out


def still(t0, t1, x, y, gesture="Open_Palm", step=33):
    return [(t, gesture, x, y) for t in range(t0, t1 + 1, step)]


def move(t0, start, end, duration, gesture="Open_Palm", steps=6):
    (x0, y0), (x1, y1) = start, end
    return [
        (t0 + duration * i // steps, gesture,
         x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        for i in range(1, steps + 1)
    ]


@pytest.mark.parametrize("start,end,expected", [
    ((0.5, 0.6), (0.5, 0.3), Direction.UP),
    ((0.5, 0.4), (0.5, 0.7), Direction.DOWN),
    ((0.6, 0.5), (0.3, 0.5), Direction.LEFT),
    ((0.4, 0.5), (0.7, 0.5), Direction.RIGHT),
])
def test_swipe_directions(start, end, expected):
    frames = still(0, 330, *start) + move(363, start, end, 200)
    result = feed(SwipeDetector(), frames)
    assert [d for _, d in result] == [expected]


def test_swipe_needs_still_palm_first():
    frames = still(0, 200, 0.5, 0.6) + move(233, (0.5, 0.6), (0.5, 0.3), 200)
    assert feed(SwipeDetector(), frames) == []


def test_swipe_needs_open_palm():
    frames = (still(0, 330, 0.5, 0.6, gesture="Closed_Fist")
              + move(363, (0.5, 0.6), (0.5, 0.3), 200, gesture="Closed_Fist"))
    assert feed(SwipeDetector(), frames) == []


def test_short_movement_is_ignored():
    frames = still(0, 330, 0.5, 0.6) + move(363, (0.5, 0.6), (0.5, 0.45), 200)
    assert feed(SwipeDetector(), frames) == []


def test_slow_movement_is_ignored():
    frames = still(0, 330, 0.5, 0.6) + move(363, (0.5, 0.6), (0.5, 0.3), 800)
    assert feed(SwipeDetector(), frames) == []


def test_label_may_change_during_motion():
    frames = still(0, 330, 0.5, 0.6) + move(363, (0.5, 0.6), (0.5, 0.3), 200, gesture=None)
    assert [d for _, d in feed(SwipeDetector(), frames)] == [Direction.UP]


def test_one_swipe_per_movement():
    frames = (still(0, 330, 0.5, 0.6)
              + move(363, (0.5, 0.6), (0.5, 0.3), 200)
              + move(596, (0.5, 0.3), (0.5, 0.0), 200))
    assert len(feed(SwipeDetector(), frames)) == 1


def test_reset_disarms():
    detector = SwipeDetector()
    feed(detector, still(0, 330, 0.5, 0.6))
    assert detector.armed
    detector.reset()
    assert not detector.armed
    assert feed(detector, move(363, (0.5, 0.6), (0.5, 0.3), 200)) == []
```

- [ ] **Step 2: Verifica che falliscano**

Run: `.venv/bin/pytest tests/test_swipe.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tv_air_remote.swipe'`

- [ ] **Step 3: Implementa `tv_air_remote/observation.py`**

```python
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
```

- [ ] **Step 4: Implementa `tv_air_remote/swipe.py`**

```python
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
```

- [ ] **Step 5: Verifica che passino**

Run: `.venv/bin/pytest tests/test_swipe.py -q`
Expected: `11 passed`

- [ ] **Step 6: Commit**

```bash
git add tv_air_remote/observation.py tv_air_remote/swipe.py tests/test_swipe.py
git commit -m "Add swipe detector"
```

---

### Task 4: Interprete delle gesture

**Files:**
- Create: `tv_air_remote/interpreter.py`
- Test: `tests/test_interpreter.py`

- [ ] **Step 1: Scrivi i test**

```python
from tv_air_remote.config import parse_config
from tv_air_remote.interpreter import GestureInterpreter
from tv_air_remote.observation import HandObservation

CENTER = (0.5, 0.5)


def make():
    return GestureInterpreter(parse_config({}, require_host=False))


def run(interp, frames):
    """frames: (t_ms, gesture | None[, wrist[, score]]). None = nessuna mano."""
    sent = []
    for frame in frames:
        t, gesture = frame[0], frame[1]
        wrist = frame[2] if len(frame) > 2 else CENTER
        score = frame[3] if len(frame) > 3 else 0.9
        obs = None if gesture is None else HandObservation(gesture, score, wrist, t)
        sent += [(t, key) for key in interp.update(obs, t)]
    return sent


def hold(gesture, t0, t1, step=33, wrist=CENTER, score=0.9):
    return [(t, gesture, wrist, score) for t in range(t0, t1 + 1, step)]


def gone(t0, t1, step=33):
    return [(t, None) for t in range(t0, t1 + 1, step)]


def swipe(t0, start, end, gesture="Open_Palm"):
    """Palmo fermo per 330 ms in start, poi movimento in 200 ms fino a end."""
    frames = hold(gesture, t0, t0 + 330, wrist=start)
    (x0, y0), (x1, y1) = start, end
    for i in range(1, 7):
        frames.append((t0 + 363 + 200 * i // 6, gesture,
                       (x0 + (x1 - x0) * i / 6, y0 + (y1 - y0) * i / 6)))
    return frames


def keys(sent):
    return [key for _, key in sent]


def enter_nav(interp):
    sent = run(interp, hold("Pointing_Up", 0, 1100, step=10) + gone(1110, 1500, step=10))
    assert keys(sent) == ["KEY_HOME"]
    assert interp.mode == "nav"


def test_gesture_needs_five_stable_frames():
    interp = make()
    assert run(interp, hold("Victory", 0, 99)) == []
    assert run(interp, [(132, "Victory")]) == [(132, "KEY_PAUSE")]


def test_low_confidence_is_ignored():
    assert run(make(), hold("Victory", 0, 1000, score=0.5)) == []


def test_victory_alternates_pause_and_play():
    sent = run(make(), hold("Victory", 0, 330) + gone(363, 1000) + hold("Victory", 1033, 1400))
    assert keys(sent) == ["KEY_PAUSE", "KEY_PLAY"]


def test_single_command_while_held():
    assert keys(run(make(), hold("Victory", 0, 3000))) == ["KEY_PAUSE"]


def test_open_palm_alone_does_nothing():
    assert run(make(), hold("Open_Palm", 0, 3000)) == []


def test_cooldown_delays_next_command():
    sent = run(make(), hold("Victory", 0, 198) + hold("Thumb_Up", 231, 1200))
    assert sent[0] == (132, "KEY_PAUSE")
    assert sent[1][1] == "KEY_VOLUP"
    assert sent[1][0] >= 132 + 800


def test_volume_repeats_and_accelerates():
    sent = run(make(), hold("Thumb_Up", 0, 3000, step=10))
    times = [t for t, key in sent if key == "KEY_VOLUP"]
    assert times[:6] == [40, 340, 640, 940, 1240, 1540]
    assert times[6] - times[5] == 150
    assert len(sent) == len(times)


def test_volume_stops_when_hand_is_lost():
    sent = run(make(), hold("Thumb_Down", 0, 500, step=10) + gone(510, 2000, step=10))
    assert all(t <= 500 for t, _ in sent)
    assert keys(sent) == ["KEY_VOLDOWN", "KEY_VOLDOWN"]


def test_power_requires_long_hold():
    assert run(make(), hold("ILoveYou", 0, 1400, step=10)) == []
    assert run(make(), hold("ILoveYou", 0, 1600, step=10)) == [(1500, "KEY_POWER")]


def test_pointing_up_toggles_navigation_mode():
    interp = make()
    enter_nav(interp)
    sent = run(interp, hold("Pointing_Up", 1510, 2600, step=10))
    assert sent == [(2510, "KEY_EXIT")]
    assert interp.mode == "tv"


def test_navigation_mode_times_out():
    interp = make()
    enter_nav(interp)
    interp.update(None, 8990)
    assert interp.mode == "nav"
    interp.update(None, 9000)
    assert interp.mode == "tv"


def test_swipe_up_changes_channel_in_tv_mode():
    assert keys(run(make(), swipe(0, (0.5, 0.6), (0.5, 0.3)))) == ["KEY_CHUP"]


def test_swipe_down_changes_channel_in_tv_mode():
    assert keys(run(make(), swipe(0, (0.5, 0.4), (0.5, 0.7)))) == ["KEY_CHDOWN"]


def test_horizontal_swipe_does_nothing_in_tv_mode():
    assert run(make(), swipe(0, (0.6, 0.5), (0.3, 0.5))) == []


def test_navigation_mode_mapping():
    interp = make()
    enter_nav(interp)
    sent = run(interp, swipe(2000, (0.6, 0.5), (0.3, 0.5)))
    sent += run(interp, gone(2700, 3100) + hold("Closed_Fist", 3133, 3400))
    sent += run(interp, gone(3433, 4300) + hold("Victory", 4333, 4600))
    sent += run(interp, gone(4633, 5500) + hold("Thumb_Up", 5533, 5700))
    assert keys(sent) == ["KEY_LEFT", "KEY_ENTER", "KEY_RETURN", "KEY_VOLUP"]


def test_swipe_cooldown():
    interp = make()
    first = run(interp, swipe(0, (0.5, 0.6), (0.5, 0.3)))
    assert keys(first) == ["KEY_CHUP"]
    fired_at = first[0][0]
    second = run(interp, hold("Open_Palm", fired_at + 10, fired_at + 320, step=10, wrist=(0.5, 0.3)))
    second += run(interp, [(fired_at + 330, "Open_Palm", (0.5, 0.45)),
                           (fired_at + 340, "Open_Palm", (0.5, 0.6))])
    assert second == []
```

- [ ] **Step 2: Verifica che falliscano**

Run: `.venv/bin/pytest tests/test_interpreter.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tv_air_remote.interpreter'`

- [ ] **Step 3: Implementa `tv_air_remote/interpreter.py`**

```python
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
```

- [ ] **Step 4: Verifica che passino**

Run: `.venv/bin/pytest tests/test_interpreter.py -q`
Expected: `16 passed`

- [ ] **Step 5: Commit**

```bash
git add tv_air_remote/interpreter.py tests/test_interpreter.py
git commit -m "Add gesture interpreter state machine"
```

---

### Task 5: Controller della TV

**Files:**
- Create: `tv_air_remote/tv.py`
- Test: `tests/test_tv.py`

- [ ] **Step 1: Scrivi i test**

```python
import time

from samsungtvws.exceptions import ConnectionFailure, UnauthorizedError

from tv_air_remote.config import TvConfig
from tv_air_remote.tv import TvController, TvStatus


class FakeRemote:
    def __init__(self, fail_open=None, fail_send=False, on_open=None):
        self.fail_open = fail_open
        self.fail_send = fail_send
        self.on_open = on_open
        self.sent = []
        self.closed = False

    def open(self):
        if self.on_open:
            self.on_open()
        if self.fail_open:
            raise self.fail_open

    def send_key(self, key):
        if self.fail_send:
            raise OSError("broken pipe")
        self.sent.append(key)

    def close(self):
        self.closed = True


def make(tmp_path, remotes, mac=None, token=True):
    token_file = tmp_path / "token"
    if token:
        token_file.write_text("abc")
    cfg = TvConfig(host="192.168.1.50", mac=mac, token_file=str(token_file))
    pending = iter(remotes)
    woken = []
    ctl = TvController(cfg, remote_factory=lambda _cfg: next(pending), wol=woken.append)
    return ctl, woken


def test_connect_and_send(tmp_path):
    remote = FakeRemote()
    ctl, _ = make(tmp_path, [remote])
    assert ctl.connect() == 0
    assert ctl.status is TvStatus.CONNECTED
    ctl.send("KEY_VOLUP")
    ctl.process_one(timeout=0)
    assert remote.sent == ["KEY_VOLUP"]


def test_backoff_doubles_up_to_30_seconds(tmp_path):
    remotes = [FakeRemote(fail_open=ConnectionFailure("off")) for _ in range(7)]
    ctl, _ = make(tmp_path, remotes)
    assert [ctl.connect() for _ in range(7)] == [1, 2, 4, 8, 16, 30, 30]
    assert ctl.status is TvStatus.DISCONNECTED
    assert all(r.closed for r in remotes)


def test_backoff_resets_after_success(tmp_path):
    remotes = [FakeRemote(fail_open=OSError("unreachable")),
               FakeRemote(fail_open=OSError("unreachable")),
               FakeRemote(),
               FakeRemote(fail_open=OSError("unreachable"))]
    ctl, _ = make(tmp_path, remotes)
    assert [ctl.connect() for _ in range(4)] == [1, 2, 0, 1]


def test_unauthorized(tmp_path):
    ctl, _ = make(tmp_path, [FakeRemote(fail_open=UnauthorizedError("denied"))])
    ctl.connect()
    assert ctl.status is TvStatus.AUTH_DENIED


def test_awaiting_auth_without_token(tmp_path):
    seen = []
    ctl, _ = make(tmp_path, [], token=False)
    remote = FakeRemote(on_open=lambda: seen.append(ctl.status))
    ctl._factory = lambda _cfg: remote
    ctl.connect()
    assert seen == [TvStatus.AWAITING_AUTH]
    assert ctl.status is TvStatus.CONNECTED


def test_commands_dropped_while_disconnected(tmp_path):
    remote = FakeRemote()
    ctl, _ = make(tmp_path, [remote])
    ctl.send("KEY_VOLUP")
    ctl.connect()
    ctl.process_one(timeout=0)
    assert remote.sent == []


def test_full_queue_drops_oldest(tmp_path):
    remote = FakeRemote()
    ctl, _ = make(tmp_path, [remote])
    ctl.connect()
    for i in range(7):
        ctl.send(f"KEY_{i}")
    for _ in range(7):
        ctl.process_one(timeout=0)
    assert remote.sent == ["KEY_2", "KEY_3", "KEY_4", "KEY_5", "KEY_6"]


def test_send_failure_disconnects(tmp_path):
    remote = FakeRemote(fail_send=True)
    ctl, _ = make(tmp_path, [remote])
    ctl.connect()
    ctl.send("KEY_CHUP")
    ctl.process_one(timeout=0)
    assert ctl.status is TvStatus.DISCONNECTED
    assert remote.closed


def test_power_sends_wake_on_lan_when_disconnected(tmp_path):
    ctl, woken = make(tmp_path, [], mac="aa:bb:cc:dd:ee:ff")
    ctl.send("KEY_VOLUP")
    ctl.send("KEY_POWER")
    assert woken == ["aa:bb:cc:dd:ee:ff"]


def test_power_without_mac_is_dropped(tmp_path):
    ctl, woken = make(tmp_path, [])
    ctl.send("KEY_POWER")
    assert woken == []


def test_background_thread(tmp_path):
    remote = FakeRemote()
    ctl, _ = make(tmp_path, [remote])
    ctl.start()
    try:
        deadline = time.monotonic() + 2
        while ctl.status is not TvStatus.CONNECTED and time.monotonic() < deadline:
            time.sleep(0.01)
        ctl.send("KEY_CHDOWN")
        while not remote.sent and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        ctl.stop()
    assert remote.sent == ["KEY_CHDOWN"]
    assert remote.closed
```

- [ ] **Step 2: Verifica che falliscano**

Run: `.venv/bin/pytest tests/test_tv.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tv_air_remote.tv'`

- [ ] **Step 3: Implementa `tv_air_remote/tv.py`**

```python
"""Invio dei tasti alla TV Samsung in un thread separato."""

from __future__ import annotations

import logging
import os
import queue
import threading
from enum import Enum
from typing import Callable, Protocol

from samsungtvws.exceptions import UnauthorizedError

from .config import TvConfig

log = logging.getLogger(__name__)

MAX_BACKOFF_S = 30.0
QUEUE_SIZE = 5
POWER_KEY = "KEY_POWER"


class TvStatus(Enum):
    CONNECTED = "connessa"
    DISCONNECTED = "non connessa"
    AWAITING_AUTH = "consenti l'accesso sulla TV"
    AUTH_DENIED = "accesso negato (vedi log)"


class Remote(Protocol):
    def open(self) -> object: ...
    def send_key(self, key: str) -> None: ...
    def close(self) -> None: ...


def samsung_remote(cfg: TvConfig) -> Remote:
    from samsungtvws import SamsungTVWS

    return SamsungTVWS(
        host=cfg.host,
        port=cfg.port,
        token_file=cfg.token_file,
        name=cfg.name,
        timeout=30,
        key_press_delay=0,
    )


def send_wol(mac: str) -> None:
    import wakeonlan

    wakeonlan.send_magic_packet(mac)


class TvController:
    """Collegamento alla TV con riconnessione automatica.

    ``send`` non blocca mai: i tasti finiscono in una coda letta da un thread
    dedicato. Con la TV non connessa i tasti vengono scartati, tranne
    ``KEY_POWER`` che, se è configurato il MAC, diventa un Wake-on-LAN.
    """

    def __init__(
        self,
        cfg: TvConfig,
        remote_factory: Callable[[TvConfig], Remote] = samsung_remote,
        wol: Callable[[str], None] = send_wol,
    ) -> None:
        self._cfg = cfg
        self._factory = remote_factory
        self._wol = wol
        self._queue: queue.Queue[str] = queue.Queue(maxsize=QUEUE_SIZE)
        self._remote: Remote | None = None
        self._backoff = 1.0
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.status = TvStatus.DISCONNECTED

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="tv-controller", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        self._close_remote()

    def send(self, key: str) -> None:
        if self.status is not TvStatus.CONNECTED:
            if key == POWER_KEY and self._cfg.mac:
                log.info("TV non connessa: invio Wake-on-LAN a %s", self._cfg.mac)
                self._wol(self._cfg.mac)
            else:
                log.info("TV %s: scartato %s", self.status.value, key)
            return
        while True:
            try:
                self._queue.put_nowait(key)
                return
            except queue.Full:
                try:
                    log.warning("Coda piena: scartato %s", self._queue.get_nowait())
                except queue.Empty:
                    pass

    def connect(self) -> float:
        """Tenta il collegamento. Restituisce i secondi di attesa prima del
        prossimo tentativo, 0 se il collegamento è riuscito."""
        if not os.path.exists(self._cfg.token_file):
            self.status = TvStatus.AWAITING_AUTH
            log.info("Primo collegamento: consenti l'accesso dalla TV")
        remote = self._factory(self._cfg)
        try:
            remote.open()
        except Exception as exc:
            _close_quietly(remote)
            if isinstance(exc, UnauthorizedError):
                self.status = TvStatus.AUTH_DENIED
                log.error(
                    "La TV ha negato l'accesso. Abilita '%s' in Impostazioni > "
                    "Generale > Gestione dispositivi esterni > Gestione "
                    "connessione dispositivi.", self._cfg.name,
                )
            else:
                self.status = TvStatus.DISCONNECTED
                log.info("TV %s non raggiungibile: %s", self._cfg.host, exc)
            wait = self._backoff
            self._backoff = min(self._backoff * 2, MAX_BACKOFF_S)
            return wait
        self._remote = remote
        self._backoff = 1.0
        self.status = TvStatus.CONNECTED
        log.info("TV %s connessa", self._cfg.host)
        return 0.0

    def process_one(self, timeout: float = 0.2) -> None:
        """Invia il prossimo tasto in coda, se c'è."""
        try:
            key = self._queue.get(timeout=timeout) if timeout else self._queue.get_nowait()
        except queue.Empty:
            return
        try:
            self._remote.send_key(key)
        except Exception as exc:
            log.warning("Invio di %s fallito: %s", key, exc)
            self._close_remote()
            self.status = TvStatus.DISCONNECTED

    def _run(self) -> None:
        while not self._stop.is_set():
            if self.status is TvStatus.CONNECTED:
                self.process_one()
            else:
                wait = self.connect()
                if wait:
                    self._stop.wait(wait)

    def _close_remote(self) -> None:
        if self._remote is not None:
            _close_quietly(self._remote)
            self._remote = None


def _close_quietly(remote: Remote) -> None:
    try:
        remote.close()
    except Exception:
        log.debug("Chiusura del collegamento fallita", exc_info=True)


class DryRunTv:
    """TV finta per --dry-run: registra i tasti senza contattare la TV."""

    status = TvStatus.CONNECTED

    def start(self) -> None:
        log.info("Modalità dry-run: nessun comando verrà inviato alla TV")

    def stop(self) -> None:
        pass

    def send(self, key: str) -> None:
        log.info("[dry-run] %s", key)
```

- [ ] **Step 4: Verifica che passino**

Run: `.venv/bin/pytest tests/test_tv.py -q`
Expected: `11 passed`

- [ ] **Step 5: Commit**

```bash
git add tv_air_remote/tv.py tests/test_tv.py
git commit -m "Add Samsung TV controller with reconnect and Wake-on-LAN"
```

---

### Task 6: Riconoscitore MediaPipe

**Files:**
- Create: `tv_air_remote/recognizer.py`
- Test: `tests/test_recognizer.py`

- [ ] **Step 1: Scrivi i test**

```python
from types import SimpleNamespace

import numpy as np
import pytest

from tv_air_remote.recognizer import (
    DEFAULT_MODEL_PATH,
    ModelError,
    best_hand,
    ensure_model,
)


def category(name, score):
    return SimpleNamespace(category_name=name, score=score)


def landmarks(x0, y0):
    return [SimpleNamespace(x=x0 + i * 0.01, y=y0) for i in range(21)]


def test_best_hand_none_when_empty():
    result = SimpleNamespace(gestures=[], hand_landmarks=[])
    assert best_hand(result, 10) is None


def test_best_hand_picks_highest_score():
    result = SimpleNamespace(
        gestures=[[category("Victory", 0.6)], [category("Thumb_Up", 0.9)]],
        hand_landmarks=[landmarks(0.1, 0.2), landmarks(0.5, 0.6)],
    )
    obs = best_hand(result, 42)
    assert obs.gesture == "Thumb_Up"
    assert obs.score == 0.9
    assert obs.wrist == (0.5, 0.6)
    assert obs.t_ms == 42
    assert len(obs.landmarks) == 21


def test_best_hand_maps_none_category():
    result = SimpleNamespace(gestures=[[category("None", 0.8)]], hand_landmarks=[landmarks(0.3, 0.3)])
    assert best_hand(result, 0).gesture is None


def test_ensure_model_keeps_existing_file(tmp_path):
    path = tmp_path / "m.task"
    path.write_bytes(b"model")
    assert ensure_model(path, url="file:///nonexistent") == path


def test_ensure_model_downloads(tmp_path):
    source = tmp_path / "source.task"
    source.write_bytes(b"model")
    path = tmp_path / "models" / "m.task"
    assert ensure_model(path, url=source.as_uri()) == path
    assert path.read_bytes() == b"model"


def test_ensure_model_download_failure(tmp_path):
    path = tmp_path / "models" / "m.task"
    with pytest.raises(ModelError, match="file:///nonexistent"):
        ensure_model(path, url="file:///nonexistent/m.task")
    assert not path.exists()
    assert not path.with_suffix(".part").exists()


@pytest.mark.skipif(not DEFAULT_MODEL_PATH.exists(), reason="modello non scaricato")
def test_recognizer_on_blank_frame():
    from tv_air_remote.recognizer import GestureRecognizer

    with GestureRecognizer(DEFAULT_MODEL_PATH) as recognizer:
        frame = np.zeros((480, 640, 3), np.uint8)
        assert recognizer.recognize(frame, 0) is None
        assert recognizer.recognize(frame, 0) is None  # timestamp ripetuto: va corretto
```

- [ ] **Step 2: Verifica che falliscano**

Run: `.venv/bin/pytest tests/test_recognizer.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tv_air_remote.recognizer'`

- [ ] **Step 3: Implementa `tv_air_remote/recognizer.py`**

```python
"""Riconoscimento delle gesture con MediaPipe Gesture Recognizer."""

from __future__ import annotations

import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .observation import HandObservation

log = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/gesture_recognizer/"
    "gesture_recognizer/float16/latest/gesture_recognizer.task"
)
DEFAULT_MODEL_PATH = Path("models") / "gesture_recognizer.task"


class ModelError(RuntimeError):
    """Modello assente e impossibile da scaricare."""


def ensure_model(path: Path = DEFAULT_MODEL_PATH, url: str = MODEL_URL) -> Path:
    """Restituisce il percorso del modello, scaricandolo se manca."""
    path = Path(path)
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(".part")
    log.info("Scarico il modello di riconoscimento in %s", path)
    try:
        urllib.request.urlretrieve(url, partial)
    except (urllib.error.URLError, OSError) as exc:
        partial.unlink(missing_ok=True)
        raise ModelError(
            f"Impossibile scaricare il modello ({exc}). "
            f"Scaricalo a mano da {url} e salvalo in {path}"
        ) from exc
    partial.replace(path)
    return path


def best_hand(result: Any, t_ms: int) -> HandObservation | None:
    """Sceglie la mano con la gesture più sicura da un GestureRecognizerResult."""
    best: HandObservation | None = None
    for categories, hand in zip(result.gestures, result.hand_landmarks):
        if not categories:
            continue
        top = categories[0]
        if best is not None and top.score <= best.score:
            continue
        points = tuple((lm.x, lm.y) for lm in hand)
        gesture = None if top.category_name in ("", "None") else top.category_name
        best = HandObservation(gesture, top.score, points[0], t_ms, points)
    return best


class GestureRecognizer:
    """MediaPipe in modalità VIDEO, una sola mano tracciata."""

    def __init__(self, model_path: Path) -> None:
        import mediapipe as mp
        from mediapipe.tasks.python import BaseOptions, vision

        self._mp = mp
        options = vision.GestureRecognizerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.VIDEO,
            num_hands=1,
        )
        self._recognizer = vision.GestureRecognizer.create_from_options(options)
        self._last_t = -1

    def recognize(self, frame_bgr: np.ndarray, t_ms: int) -> HandObservation | None:
        # MediaPipe richiede timestamp strettamente crescenti.
        t_ms = max(t_ms, self._last_t + 1)
        self._last_t = t_ms
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        return best_hand(self._recognizer.recognize_for_video(image, t_ms), t_ms)

    def close(self) -> None:
        self._recognizer.close()

    def __enter__(self) -> GestureRecognizer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
```

- [ ] **Step 4: Scarica il modello e verifica che i test passino**

Run: `.venv/bin/python -c "from tv_air_remote.recognizer import ensure_model; ensure_model()" && .venv/bin/pytest tests/test_recognizer.py -q`
Expected: `7 passed` (su Linux senza `libEGL` MediaPipe non si carica: installare `libegl1 libgles2`).

- [ ] **Step 5: Commit**

```bash
git add tv_air_remote/recognizer.py tests/test_recognizer.py
git commit -m "Add MediaPipe gesture recognizer wrapper"
```

---

### Task 7: Webcam e overlay

**Files:**
- Create: `tv_air_remote/camera.py`, `tv_air_remote/overlay.py`
- Test: `tests/test_camera.py`, `tests/test_overlay.py`

- [ ] **Step 1: Scrivi i test**

`tests/test_camera.py`:
```python
import numpy as np
import pytest

from tv_air_remote import camera as camera_module
from tv_air_remote.camera import Camera, CameraError


class FakeCapture:
    def __init__(self, opened=True, frame=None):
        self.opened = opened
        self.frame = frame
        self.released = False
        self.props = {}

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        self.props[prop] = value

    def read(self):
        return (self.frame is not None), self.frame

    def release(self):
        self.released = True


def install(monkeypatch, capture):
    monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda index: capture)


def test_camera_not_available(monkeypatch):
    capture = FakeCapture(opened=False)
    install(monkeypatch, capture)
    with pytest.raises(CameraError, match="indice 3"):
        Camera(index=3)
    assert capture.released


def test_read_mirrors_frame(monkeypatch):
    frame = np.zeros((2, 3, 3), np.uint8)
    frame[0, 0] = 255
    install(monkeypatch, FakeCapture(frame=frame))
    image, t_ms = Camera().read()
    assert image[0, 2].tolist() == [255, 255, 255]
    assert isinstance(t_ms, int)


def test_read_failure_returns_none(monkeypatch):
    install(monkeypatch, FakeCapture(frame=None))
    assert Camera().read() is None
```

`tests/test_overlay.py`:
```python
import numpy as np

from tv_air_remote.observation import HandObservation
from tv_air_remote.overlay import draw


def test_draw_changes_frame_and_keeps_shape():
    frame = np.zeros((480, 640, 3), np.uint8)
    points = tuple((0.3 + i * 0.01, 0.5) for i in range(21))
    obs = HandObservation("Thumb_Up", 0.9, points[0], 0, points)
    out = draw(frame, obs, "nav", "Thumb_Up", "KEY_VOLUP", "connessa")
    assert out.shape == (480, 640, 3)
    assert out.any()


def test_draw_without_hand():
    frame = np.zeros((480, 640, 3), np.uint8)
    assert draw(frame, None, "tv", None, None, "non connessa").any()
```

- [ ] **Step 2: Verifica che falliscano**

Run: `.venv/bin/pytest tests/test_camera.py tests/test_overlay.py -q`
Expected: FAIL con `ModuleNotFoundError`

- [ ] **Step 3: Implementa `tv_air_remote/camera.py`**

```python
"""Acquisizione dei frame dalla webcam."""

from __future__ import annotations

import time

import cv2
import numpy as np


class CameraError(RuntimeError):
    """Webcam assente o non funzionante."""


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, fps: int = 30) -> None:
        self._cap = cv2.VideoCapture(index)
        if not self._cap.isOpened():
            self._cap.release()
            raise CameraError(
                f"Impossibile aprire la webcam con indice {index}. "
                "Prova un altro indice con --camera N."
            )
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._cap.set(cv2.CAP_PROP_FPS, fps)

    def read(self) -> tuple[np.ndarray, int] | None:
        """Frame specchiato (sinistra dell'utente = sinistra a schermo) e
        timestamp monotono in ms, oppure None se la lettura fallisce."""
        ok, frame = self._cap.read()
        if not ok:
            return None
        return cv2.flip(frame, 1), int(time.monotonic() * 1000)

    def close(self) -> None:
        self._cap.release()
```

- [ ] **Step 4: Implementa `tv_air_remote/overlay.py`**

```python
"""Informazioni disegnate sopra l'immagine della webcam."""

from __future__ import annotations

import cv2
import numpy as np

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
LINE_HEIGHT = 22
PANEL_ALPHA = 0.55


def draw(
    frame: np.ndarray,
    obs: HandObservation | None,
    mode: str,
    gesture: str | None,
    last_key: str | None,
    tv_status: str,
) -> np.ndarray:
    height, width = frame.shape[:2]
    if obs is not None and obs.landmarks:
        points = [(int(x * width), int(y * height)) for x, y in obs.landmarks]
        for a, b in HAND_CONNECTIONS:
            if a < len(points) and b < len(points):
                cv2.line(frame, points[a], points[b], (0, 255, 0), 2)
        for point in points:
            cv2.circle(frame, point, 3, (0, 0, 255), -1)

    lines = [
        f"Modalita': {MODE_LABELS.get(mode, mode)}",
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
    return frame
```

- [ ] **Step 5: Verifica che passino**

Run: `.venv/bin/pytest tests/test_camera.py tests/test_overlay.py -q`
Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add tv_air_remote/camera.py tv_air_remote/overlay.py tests/test_camera.py tests/test_overlay.py
git commit -m "Add webcam capture and on-screen overlay"
```

---

### Task 8: CLI e ciclo principale

**Files:**
- Create: `tv_air_remote/__main__.py`, `config.example.yaml`
- Test: `tests/test_main.py`

- [ ] **Step 1: Scrivi i test**

```python
from pathlib import Path

from tv_air_remote.__main__ import build_config, main, parse_args


def test_parse_args_defaults():
    args = parse_args([])
    assert args.config == "config.yaml"
    assert args.camera is None
    assert not args.dry_run


def test_dry_run_without_config_uses_defaults(tmp_path):
    args = parse_args(["--dry-run", "--config", str(tmp_path / "missing.yaml")])
    assert build_config(args).tv.host == "dry-run"


def test_missing_config_exits_with_error(tmp_path, caplog):
    assert main(["--config", str(tmp_path / "missing.yaml")]) == 1
    assert "config.example.yaml" in caplog.text


def test_example_config_is_valid():
    example = Path(__file__).resolve().parent.parent / "config.example.yaml"
    args = parse_args(["--config", str(example)])
    cfg = build_config(args)
    assert cfg.tv.port == 8002
    assert cfg.mapping["tv"]["Victory"].key == "PLAY_PAUSE"
```

- [ ] **Step 2: Verifica che falliscano**

Run: `.venv/bin/pytest tests/test_main.py -q`
Expected: FAIL con `ModuleNotFoundError: No module named 'tv_air_remote.__main__'`

- [ ] **Step 3: Implementa `tv_air_remote/__main__.py`**

```python
"""Avvio: python -m tv_air_remote."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import cv2

from .camera import Camera, CameraError
from .config import Config, ConfigError, load_config, parse_config
from .interpreter import GestureInterpreter
from .overlay import draw
from .recognizer import DEFAULT_MODEL_PATH, GestureRecognizer, ModelError, ensure_model
from .tv import DryRunTv, TvController

WINDOW = "TV Air Remote"
MAX_READ_FAILURES = 30
QUIT_KEYS = (ord("q"), 27)  # q, ESC

log = logging.getLogger("tv_air_remote")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m tv_air_remote",
        description="Controlla una Smart TV Samsung con le gesture delle mani.",
    )
    parser.add_argument("--config", default="config.yaml", help="file di configurazione YAML")
    parser.add_argument("--camera", type=int, help="indice della webcam (sovrascrive la config)")
    parser.add_argument("--dry-run", action="store_true",
                        help="non contatta la TV: mostra solo i tasti che invierebbe")
    parser.add_argument("--model", default=str(DEFAULT_MODEL_PATH),
                        help="percorso del modello MediaPipe")
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> Config:
    path = Path(args.config)
    if args.dry_run and not path.exists():
        return parse_config({}, require_host=False)
    return load_config(path)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    args = parse_args(argv)
    try:
        config = build_config(args)
        model = ensure_model(Path(args.model))
        cam = config.camera
        camera = Camera(args.camera if args.camera is not None else cam.index,
                        cam.width, cam.height, cam.fps)
    except (ConfigError, ModelError, CameraError) as exc:
        log.error("%s", exc)
        return 1

    tv = DryRunTv() if args.dry_run else TvController(config.tv)
    interpreter = GestureInterpreter(config)
    tv.start()
    try:
        with GestureRecognizer(model) as recognizer:
            run_loop(camera, recognizer, interpreter, tv)
    except CameraError as exc:
        log.error("%s", exc)
        return 1
    finally:
        camera.close()
        tv.stop()
        cv2.destroyAllWindows()
    return 0


def run_loop(camera, recognizer, interpreter, tv) -> None:
    last_key = None
    failures = 0
    while True:
        item = camera.read()
        if item is None:
            failures += 1
            if failures >= MAX_READ_FAILURES:
                raise CameraError("La webcam ha smesso di fornire immagini")
            continue
        failures = 0
        frame, t_ms = item
        obs = recognizer.recognize(frame, t_ms)
        for key in interpreter.update(obs, t_ms):
            log.info("%s -> %s", interpreter.gesture or "swipe", key)
            tv.send(key)
            last_key = key
        draw(frame, obs, interpreter.mode, interpreter.gesture, last_key, tv.status.value)
        cv2.imshow(WINDOW, frame)
        if cv2.waitKey(1) & 0xFF in QUIT_KEYS:
            return


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Crea `config.example.yaml`**

```yaml
# Copia questo file in config.yaml e modifica almeno tv.host.

tv:
  host: 192.168.1.50          # IP della TV (Impostazioni > Generale > Rete > Stato rete)
  port: 8002                  # 8002 = WebSocket sicuro (TV dal 2016 in poi)
  # mac: "aa:bb:cc:dd:ee:ff"  # per accendere la TV con Wake-on-LAN
  token_file: .tv_token       # creato al primo collegamento autorizzato
  name: TV Air Remote         # nome mostrato sulla TV

camera:
  index: 0
  width: 640
  height: 480
  fps: 30

# Valori predefiniti: cambiali solo se serve.
thresholds:
  min_score: 0.7          # confidenza minima della gesture
  stable_frames: 5        # frame consecutivi per confermare una gesture
  cooldown_ms: 800        # pausa dopo un comando singolo
  swipe_cooldown_ms: 500  # pausa dopo uno swipe
  repeat_ms: 300          # ripetizione del volume
  fast_repeat_ms: 150     # ripetizione veloce del volume
  fast_after_ms: 1500     # dopo quanto il volume accelera
  hand_lost_ms: 300       # mano assente oltre questo tempo = reset
  nav_timeout_ms: 8000    # ritorno automatico alla modalità TV
  swipe_arm_ms: 300       # palmo fermo prima di uno swipe
  swipe_still_dist: 0.03  # "fermo" = polso entro il 3% del frame
  swipe_min_dist: 0.25    # swipe = spostamento oltre il 25% del frame...
  swipe_max_ms: 400       # ...entro questo tempo
  repeat_gestures: [Thumb_Up, Thumb_Down]
  hold_ms:
    Pointing_Up: 1000
    ILoveYou: 1500

# Gesture: Thumb_Up, Thumb_Down, Victory, Pointing_Up, ILoveYou, Closed_Fist,
# Open_Palm, SWIPE_UP, SWIPE_DOWN, SWIPE_LEFT, SWIPE_RIGHT.
# Valore: un tasto Samsung (KEY_...), PLAY_PAUSE, oppure {key: ..., switch_to: tv|nav}.
# Una modalità scritta qui sostituisce per intero quella predefinita.
mapping:
  tv:
    SWIPE_UP: KEY_CHUP
    SWIPE_DOWN: KEY_CHDOWN
    Thumb_Up: KEY_VOLUP
    Thumb_Down: KEY_VOLDOWN
    Victory: PLAY_PAUSE
    Pointing_Up: {key: KEY_HOME, switch_to: nav}
    ILoveYou: KEY_POWER
  nav:
    SWIPE_UP: KEY_UP
    SWIPE_DOWN: KEY_DOWN
    SWIPE_LEFT: KEY_LEFT
    SWIPE_RIGHT: KEY_RIGHT
    Closed_Fist: KEY_ENTER
    Victory: KEY_RETURN
    Thumb_Up: KEY_VOLUP
    Thumb_Down: KEY_VOLDOWN
    Pointing_Up: {key: KEY_EXIT, switch_to: tv}
    ILoveYou: KEY_POWER
```

- [ ] **Step 5: Verifica che passino**

Run: `.venv/bin/pytest tests/test_main.py -q`
Expected: `4 passed`

- [ ] **Step 6: Commit**

```bash
git add tv_air_remote/__main__.py config.example.yaml tests/test_main.py
git commit -m "Add CLI entry point and example configuration"
```

---

### Task 9: README e verifica finale

**Files:**
- Create: `README.md`

- [ ] **Step 1: Scrivi `README.md`** con queste sezioni: descrizione; requisiti (Python 3.11/3.12, webcam, TV Samsung Tizen sulla stessa rete); installazione (`python -m venv .venv`, `pip install -e .`); configurazione (copiare `config.example.yaml`, IP, MAC e Wake-on-LAN, prima autorizzazione); avvio (`python -m tv_air_remote`, `--dry-run`, `--camera`); tabelle delle gesture per modalità; consigli d'uso (luce, distanza 1-3 m, mano ben visibile); checklist di test manuale in `--dry-run`; risoluzione problemi (TV non connessa, accesso negato, webcam, play/pausa sfasato, timeshift USB); sviluppo (`pip install -e ".[dev]"`, `pytest`).

- [ ] **Step 2: Esegui tutta la suite**

Run: `.venv/bin/pytest -q`
Expected: tutti i test passano (67).

- [ ] **Step 3: Commit e push**

```bash
git add README.md
git commit -m "Add README with setup, gestures and manual test checklist"
git push -u origin ccr-b0bfcb14-z0e6al
```
