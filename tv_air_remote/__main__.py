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
from .overlay import JoystickView, draw, legend
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
            run_loop(camera, recognizer, interpreter, tv, commands_by_mode(config))
    except CameraError as exc:
        log.error("%s", exc)
        return 1
    finally:
        camera.close()
        tv.stop()
        cv2.destroyAllWindows()
    return 0


def commands_by_mode(config: Config) -> dict[str, list[tuple[str, str]]]:
    return {mode: legend(actions, config.thresholds.hold_ms)
            for mode, actions in config.mapping.items()}


def joystick_views(interpreter: GestureInterpreter) -> list[JoystickView]:
    return [JoystickView(joy.center, joy.zone, joy.direction.value if joy.direction else None)
            for joy in interpreter.joysticks.values() if joy.center is not None]


def run_loop(camera, recognizer, interpreter, tv, commands=None) -> None:
    commands = commands or {}
    mode = interpreter.mode
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
        hands = recognizer.recognize(frame, t_ms)
        for key in interpreter.update(hands, t_ms):
            source = f"[{interpreter.last_source}]" if interpreter.last_source else ""
            log.info("%s%s -> %s", interpreter.gesture or "-", source, key)
            tv.send(key)
            last_key = key
        if interpreter.mode != mode:
            mode = interpreter.mode
            log.info("Modalita' -> %s", mode)
        draw(frame, hands, interpreter.mode, interpreter.gesture, last_key, tv.status.value,
             commands.get(interpreter.mode, []), joystick_views(interpreter))
        cv2.imshow(WINDOW, frame)
        if cv2.waitKey(1) & 0xFF in QUIT_KEYS:
            return


if __name__ == "__main__":
    sys.exit(main())
