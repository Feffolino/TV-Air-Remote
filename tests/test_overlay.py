import numpy as np

from tv_air_remote.observation import HandObservation
from tv_air_remote.overlay import draw


def test_draw_changes_frame_and_keeps_shape():
    frame = np.zeros((480, 640, 3), np.uint8)
    points = tuple((0.3 + i * 0.01, 0.5) for i in range(21))
    obs = HandObservation("Thumb_Up", 0.9, points[0], 0, points)
    out = draw(frame, [obs], "nav", "Thumb_Up", "KEY_VOLUP", "connected")
    assert out.shape == (480, 640, 3)
    assert out.any()


def test_draw_without_hand():
    frame = np.zeros((480, 640, 3), np.uint8)
    assert draw(frame, [], "tv", None, None, "disconnected").any()


def test_legend_lists_commands_of_the_mode():
    from tv_air_remote.config import parse_config
    from tv_air_remote.overlay import legend

    cfg = parse_config({}, require_host=False)
    nav = dict(legend(cfg.mapping["nav"], cfg.thresholds.hold_ms))
    assert nav["Thumb_Up"] == "Thumb up: OK (pause/play in videos)"
    assert nav["PALM_LEFT"] == "Palm left: arrow left"
    tv_cmds = dict(legend(cfg.mapping["tv"], cfg.thresholds.hold_ms))
    assert tv_cmds["Closed_Fist"] == "Fist (hold 1 s): Home"
    assert "Closed_Fist" not in nav
    tv = [name for name, _ in legend(cfg.mapping["tv"], cfg.thresholds.hold_ms)]
    assert tv[:2] == ["PALM_UP", "PALM_DOWN"]  # palm moves before gestures


def test_legend_in_italian():
    from tv_air_remote.config import parse_config
    from tv_air_remote.overlay import legend

    cfg = parse_config({}, require_host=False)
    tv_cmds = dict(legend(cfg.mapping["tv"], cfg.thresholds.hold_ms, "it"))
    assert tv_cmds["Closed_Fist"] == "Pugno (tieni 1 s): Home"
    assert tv_cmds["PALM_UP"] == "Palmo su: volume +"


def test_every_language_has_every_text():
    from tv_air_remote.i18n import TEXTS

    reference = TEXTS["en"]
    for language, texts in TEXTS.items():
        assert texts.keys() == reference.keys(), language
        for key, value in reference.items():
            if isinstance(value, dict):
                assert texts[key].keys() == value.keys(), (language, key)


def test_unknown_names_fall_back_to_raw_text():
    from tv_air_remote.config import Action
    from tv_air_remote.overlay import legend

    assert legend({"Open_Palm": Action("KEY_MUTE")}, {}) == [("Open_Palm", "Open palm: KEY_MUTE")]


def test_draw_with_legend_writes_bottom_of_frame():
    frame = np.zeros((480, 640, 3), np.uint8)
    draw(frame, [], "nav", "Thumb_Up", None, "connected",
         [("Thumb_Up", "Thumb up: OK"), ("Victory", "Victory: back")])
    assert frame[400:].any()


def test_draw_in_italian():
    frame = np.zeros((480, 640, 3), np.uint8)
    assert draw(frame, [], "nav", None, None, "connected", language="it").any()


def test_draw_joystick_and_two_hands():
    from tv_air_remote.overlay import JoystickView

    frame = np.zeros((480, 640, 3), np.uint8)
    points = tuple((0.3 + i * 0.01, 0.5) for i in range(21))
    other = tuple((0.1, 0.5 + i * 0.01) for i in range(21))
    hands = [HandObservation("Open_Palm", 0.9, points[0], 0, points),
             HandObservation(None, 0.6, other[0], 0, other)]
    draw(frame, hands, "nav", "Open_Palm", None, "connected",
         joysticks=[JoystickView((0.5, 0.5), 0.12, "RIGHT"), JoystickView((0.2, 0.5), 0.12, None)])
    # Yellow arrow pointing right, starting from the centre of the joystick.
    assert (frame[240, 330:390] == (0, 255, 255)).all(axis=1).any()
