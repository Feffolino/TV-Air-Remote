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
    # Values are ids: the overlay shows them translated (see i18n.py).
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    AWAITING_AUTH = "awaiting_auth"
    AUTH_DENIED = "auth_denied"


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
                log.info("TV not connected: sending Wake-on-LAN to %s", self._cfg.mac)
                self._wol(self._cfg.mac)
            else:
                log.info("TV %s: dropped %s", self.status.value, key)
            return
        while True:
            try:
                self._queue.put_nowait(key)
                return
            except queue.Full:
                try:
                    log.warning("Queue full: dropped %s", self._queue.get_nowait())
                except queue.Empty:
                    pass

    def connect(self) -> float:
        """Tenta il collegamento. Restituisce i secondi di attesa prima del
        prossimo tentativo, 0 se il collegamento è riuscito."""
        if not os.path.exists(self._cfg.token_file):
            self.status = TvStatus.AWAITING_AUTH
            log.info("First connection: allow access on the TV")
        remote = self._factory(self._cfg)
        try:
            remote.open()
        except Exception as exc:
            _close_quietly(remote)
            if isinstance(exc, UnauthorizedError):
                self.status = TvStatus.AUTH_DENIED
                log.error(
                    "The TV denied access. Enable '%s' in Settings > General > "
                    "External Device Manager > Device Connection Manager.",
                    self._cfg.name,
                )
            else:
                self.status = TvStatus.DISCONNECTED
                log.info("TV %s not reachable: %s", self._cfg.host, exc)
            wait = self._backoff
            self._backoff = min(self._backoff * 2, MAX_BACKOFF_S)
            return wait
        self._remote = remote
        self._backoff = 1.0
        self.status = TvStatus.CONNECTED
        log.info("TV %s connected", self._cfg.host)
        return 0.0

    def process_one(self, timeout: float = 0.2) -> None:
        """Invia il prossimo tasto in coda, se c'è."""
        try:
            key = self._queue.get(timeout=timeout) if timeout else self._queue.get_nowait()
        except queue.Empty:
            return
        if self._try_send(key):
            return
        # La TV chiude i collegamenti inattivi: ci si riconnette e si rinvia
        # il tasto una sola volta, così la gesture non va persa.
        if self.connect() == 0.0 and self._try_send(key):
            log.info("Resent %s after reconnecting", key)

    def _try_send(self, key: str) -> bool:
        try:
            self._remote.send_key(key)
        except Exception as exc:
            log.warning("Sending %s failed: %s", key, exc)
            self._close_remote()
            self.status = TvStatus.DISCONNECTED
            return False
        return True

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
        log.debug("Closing the connection failed", exc_info=True)


class DryRunTv:
    """TV finta per --dry-run: registra i tasti senza contattare la TV."""

    status = TvStatus.CONNECTED

    def start(self) -> None:
        log.info("Dry run: no command will be sent to the TV")

    def stop(self) -> None:
        pass

    def send(self, key: str) -> None:
        log.info("[dry-run] %s", key)
