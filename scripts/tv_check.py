"""Prova del collegamento alla TV senza webcam.

    python scripts/tv_check.py                 # rete + collegamento (pairing al primo avvio)
    python scripts/tv_check.py --key KEY_MUTE  # invia anche un tasto
    python scripts/tv_check.py --wol           # invia solo il Wake-on-LAN
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
from pathlib import Path

from tv_air_remote.config import ConfigError, load_config
from tv_air_remote.tv import TvController, TvStatus, send_wol

log = logging.getLogger("tv_check")


def port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    with socket.socket() as s:
        s.settimeout(timeout)
        return s.connect_ex((host, port)) == 0


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    parser = argparse.ArgumentParser(description="Prova il collegamento alla TV.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--key", help="tasto da inviare dopo il collegamento (es. KEY_MUTE)")
    parser.add_argument("--wol", action="store_true", help="invia solo il Wake-on-LAN")
    args = parser.parse_args()

    try:
        cfg = load_config(Path(args.config)).tv
    except ConfigError as exc:
        log.error("%s", exc)
        return 1

    if args.wol:
        if not cfg.mac:
            log.error("tv.mac non impostato in %s", args.config)
            return 1
        send_wol(cfg.mac)
        log.info("Wake-on-LAN inviato a %s", cfg.mac)
        return 0

    for port in (8001, 8002):
        log.info("Porta %d: %s", port, "aperta" if port_open(cfg.host, port) else "chiusa")

    tv = TvController(cfg)
    if not Path(cfg.token_file).exists():
        log.info("Nessun token: conferma la richiesta sulla TV entro 30 s")
    wait = tv.connect()
    if tv.status is not TvStatus.CONNECTED:
        log.error("Collegamento fallito (%s), riprova tra %.0f s", tv.status.value, wait)
        return 1
    log.info("Token salvato in %s", cfg.token_file)

    if args.key:
        tv.send(args.key)
        tv.process_one(timeout=0)
        time.sleep(0.5)
        log.info("Inviato %s", args.key)
    tv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
