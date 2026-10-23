from types import SimpleNamespace

import numpy as np
import pytest

from tv_air_remote.recognizer import (
    DEFAULT_MODEL_PATH,
    ModelError,
    hands,
    ensure_model,
)


def category(name, score):
    return SimpleNamespace(category_name=name, score=score)


def landmarks(x0, y0):
    return [SimpleNamespace(x=x0 + i * 0.01, y=y0) for i in range(21)]


def test_hands_empty():
    result = SimpleNamespace(gestures=[], hand_landmarks=[])
    assert hands(result, 10) == []


def test_hands_returns_every_hand():
    result = SimpleNamespace(
        gestures=[[category("Victory", 0.6)], [category("Thumb_Up", 0.9)]],
        hand_landmarks=[landmarks(0.1, 0.2), landmarks(0.5, 0.6)],
    )
    first, second = hands(result, 42)
    assert first.gesture == "Victory"
    assert second.gesture == "Thumb_Up"
    assert second.score == 0.9
    assert second.wrist == (0.5, 0.6)
    assert second.t_ms == 42
    assert len(second.landmarks) == 21


def test_hands_maps_none_category():
    result = SimpleNamespace(gestures=[[category("None", 0.8)]], hand_landmarks=[landmarks(0.3, 0.3)])
    assert hands(result, 0)[0].gesture is None


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
        assert recognizer.recognize(frame, 0) == []
        assert recognizer.recognize(frame, 0) == []  # timestamp ripetuto: va corretto
