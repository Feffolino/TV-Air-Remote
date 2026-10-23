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
    assert cfg.thresholds.hold_ms == {"Closed_Fist": 1000, "ILoveYou": 1500}
    assert cfg.mapping["tv"]["PALM_UP"] == Action("KEY_VOLUP")
    assert cfg.mapping["tv"]["PALM_RIGHT"] == Action("KEY_CHUP")
    assert cfg.mapping["nav"]["PALM_LEFT"] == Action("KEY_LEFT")
    assert cfg.mapping["tv"]["Closed_Fist"] == Action("KEY_HOME")
    assert cfg.mapping["nav"]["Thumb_Up"] == Action("KEY_ENTER")


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
        "    Pointing_Up: {key: KEY_HOME}\n",
    ))
    assert cfg.mapping["tv"] == {
        "Closed_Fist": Action("KEY_MUTE"),
        "Pointing_Up": Action("KEY_HOME"),
    }
    assert cfg.mapping["nav"]["Thumb_Up"] == Action("KEY_ENTER")


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


def test_switch_to_is_no_longer_supported(tmp_path):
    # La modalità ora dipende dal numero di mani, non da una gesture.
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



def test_old_swipe_thresholds_are_rejected(tmp_path):
    with pytest.raises(ConfigError, match="swipe_min_dist"):
        load_config(write(tmp_path, "tv:\n  host: 1.2.3.4\nthresholds:\n  swipe_min_dist: 0.15\n"))


def test_ui_language_defaults_to_english_and_can_be_italian(tmp_path):
    assert load_config(write(tmp_path, "tv:\n  host: 1.2.3.4\n")).ui.language == "en"
    cfg = load_config(write(tmp_path, "tv:\n  host: 1.2.3.4\nui:\n  language: it\n"))
    assert cfg.ui.language == "it"


def test_unknown_ui_language(tmp_path):
    with pytest.raises(ConfigError, match="fr"):
        load_config(write(tmp_path, "tv:\n  host: 1.2.3.4\nui:\n  language: fr\n"))
