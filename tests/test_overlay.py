import numpy as np

from tv_air_remote.observation import HandObservation
from tv_air_remote.overlay import draw


def test_draw_changes_frame_and_keeps_shape():
    frame = np.zeros((480, 640, 3), np.uint8)
    points = tuple((0.3 + i * 0.01, 0.5) for i in range(21))
    obs = HandObservation("Thumb_Up", 0.9, points[0], 0, points)
    out = draw(frame, obs, "nav", "Thumb_Up", "KEY_VOLUP", "connessa")
    assert out.shape == (480, 640, 3)
    assert out.any()


def test_draw_without_hand():
    frame = np.zeros((480, 640, 3), np.uint8)
    assert draw(frame, None, "tv", None, None, "non connessa").any()
