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
    ctl, _ = make(tmp_path, [remote, FakeRemote(fail_open=OSError("unreachable"))])
    ctl.connect()
    ctl.send("KEY_CHUP")
    ctl.process_one(timeout=0)
    assert ctl.status is TvStatus.DISCONNECTED
    assert remote.closed


def test_send_failure_reconnects_and_resends(tmp_path):
    # La TV chiude il collegamento inattivo: il tasto non deve andare perso.
    stale, fresh = FakeRemote(fail_send=True), FakeRemote()
    ctl, _ = make(tmp_path, [stale, fresh])
    ctl.connect()
    ctl.send("KEY_ENTER")
    ctl.process_one(timeout=0)
    assert fresh.sent == ["KEY_ENTER"]
    assert stale.closed
    assert ctl.status is TvStatus.CONNECTED


def test_resend_happens_only_once(tmp_path):
    first, second = FakeRemote(fail_send=True), FakeRemote(fail_send=True)
    ctl, _ = make(tmp_path, [first, second])
    ctl.connect()
    ctl.send("KEY_ENTER")
    ctl.process_one(timeout=0)
    assert ctl.status is TvStatus.DISCONNECTED
    assert first.closed and second.closed


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
