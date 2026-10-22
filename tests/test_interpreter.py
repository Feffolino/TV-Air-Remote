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
