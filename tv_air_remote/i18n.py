"""On-screen texts in the supported languages.

OpenCV's Hershey fonts have no accented letters, so Italian texts use an
apostrophe instead (e.g. "giu'").
"""

from __future__ import annotations

PLAY_PAUSE = "PLAY_PAUSE"  # same value as config.PLAY_PAUSE (no import: avoids a cycle)
DEFAULT_LANGUAGE = "en"

TEXTS: dict[str, dict[str, dict[str, str] | str]] = {
    "en": {
        "mode": "Mode",
        "gesture": "Gesture",
        "last_key": "Last key",
        "tv": "TV",
        "hold": "hold {seconds:g} s",
        "modes": {"tv": "TV", "nav": "Navigation"},
        "mode_hints": {"tv": "1 hand", "nav": "2 hands"},
        "status": {
            "connected": "connected",
            "disconnected": "not connected",
            "awaiting_auth": "allow access on the TV",
            "auth_denied": "access denied (see log)",
            "dry_run": "dry run",
        },
        "gestures": {
            "PALM_UP": "Palm up",
            "PALM_DOWN": "Palm down",
            "PALM_LEFT": "Palm left",
            "PALM_RIGHT": "Palm right",
            "PALM_CLICK": "Close and open your hand",
            "Thumb_Up": "Thumb up",
            "Thumb_Down": "Thumb down",
            "Thumb_Left": "Thumb left",
            "Victory": "Victory",
            "Pointing_Up": "Index up",
            "ILoveYou": "Thumb+index+pinky",
            "Closed_Fist": "Fist",
            "Open_Palm": "Open palm",
        },
        "keys": {
            PLAY_PAUSE: "pause / play",
            "KEY_CHUP": "channel +",
            "KEY_CHDOWN": "channel -",
            "KEY_VOLUP": "volume +",
            "KEY_VOLDOWN": "volume -",
            "KEY_HOME": "Home",
            "KEY_POWER": "power on / off",
            "KEY_UP": "arrow up",
            "KEY_DOWN": "arrow down",
            "KEY_LEFT": "arrow left",
            "KEY_RIGHT": "arrow right",
            "KEY_ENTER": "OK (pause/play in videos)",
            "KEY_RETURN": "back",
            "KEY_EXIT": "exit",
        },
    },
    "it": {
        "mode": "Modalita'",
        "gesture": "Gesture",
        "last_key": "Ultimo tasto",
        "tv": "TV",
        "hold": "tieni {seconds:g} s",
        "modes": {"tv": "TV", "nav": "Navigazione"},
        "mode_hints": {"tv": "1 mano", "nav": "2 mani"},
        "status": {
            "connected": "connessa",
            "disconnected": "non connessa",
            "awaiting_auth": "consenti l'accesso sulla TV",
            "auth_denied": "accesso negato (vedi log)",
            "dry_run": "prova (dry run)",
        },
        "gestures": {
            "PALM_UP": "Palmo su",
            "PALM_DOWN": "Palmo giu'",
            "PALM_LEFT": "Palmo a sinistra",
            "PALM_RIGHT": "Palmo a destra",
            "PALM_CLICK": "Chiudi e riapri la mano",
            "Thumb_Up": "Pollice su",
            "Thumb_Down": "Pollice giu'",
            "Thumb_Left": "Pollice a sinistra",
            "Victory": "Vittoria",
            "Pointing_Up": "Indice su",
            "ILoveYou": "Pollice+indice+mignolo",
            "Closed_Fist": "Pugno",
            "Open_Palm": "Palmo aperto",
        },
        "keys": {
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
        },
    },
}
LANGUAGES = tuple(TEXTS)


def texts(language: str) -> dict:
    """Texts for a language, falling back to English."""
    return TEXTS.get(language, TEXTS[DEFAULT_LANGUAGE])
