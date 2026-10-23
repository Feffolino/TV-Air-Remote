"""Check the connection to the TV without a webcam.

    python scripts/tv_check.py                 # network + connection (pairing on first run)
    python scripts/tv_check.py --key KEY_MUTE  # also send a key
    python scripts/tv_check.py --wol           # only send Wake-on-LAN
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
    parser = argparse.ArgumentParser(description="Check the connection to the TV.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--key", help="key to send once connected (e.g. KEY_MUTE)")
    parser.add_argument("--wol", action="store_true", help="only send Wake-on-LAN")
    args = parser.parse_args()

    try:
        cfg = load_config(Path(args.config)).tv
    except ConfigError as exc:
        log.error("%s", exc)
        return 1

    if args.wol:
        if not cfg.mac:
            log.error("tv.mac is not set in %s", args.config)
            return 1
        send_wol(cfg.mac)
        log.info("Wake-on-LAN sent to %s", cfg.mac)
        return 0

    for port in (8001, 8002):
        log.info("Port %d: %s", port, "open" if port_open(cfg.host, port) else "closed")

    tv = TvController(cfg)
    if not Path(cfg.token_file).exists():
        log.info("No token yet: accept the request on the TV within 30 s")
    wait = tv.connect()
    if tv.status is not TvStatus.CONNECTED:
        log.error("Connection failed (%s), retry in %.0f s", tv.status.value, wait)
        return 1
    log.info("Token saved to %s", cfg.token_file)

    if args.key:
        tv.send(args.key)
        tv.process_one(timeout=0)
        time.sleep(0.5)
        log.info("Sent %s", args.key)
    tv.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
