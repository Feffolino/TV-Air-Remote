import numpy as np
import pytest

from tv_air_remote import camera as camera_module
from tv_air_remote.camera import Camera, CameraError


class FakeCapture:
    def __init__(self, opened=True, frame=None):
        self.opened = opened
        self.frame = frame
        self.released = False
        self.props = {}

    def isOpened(self):
        return self.opened

    def set(self, prop, value):
        self.props[prop] = value

    def read(self):
        return (self.frame is not None), self.frame

    def release(self):
        self.released = True


def install(monkeypatch, capture):
    monkeypatch.setattr(camera_module.cv2, "VideoCapture", lambda index: capture)


def test_camera_not_available(monkeypatch):
    capture = FakeCapture(opened=False)
    install(monkeypatch, capture)
    with pytest.raises(CameraError, match="indice 3"):
        Camera(index=3)
    assert capture.released


def test_read_mirrors_frame(monkeypatch):
    frame = np.zeros((2, 3, 3), np.uint8)
    frame[0, 0] = 255
    install(monkeypatch, FakeCapture(frame=frame))
    image, t_ms = Camera().read()
    assert image[0, 2].tolist() == [255, 255, 255]
    assert isinstance(t_ms, int)


def test_read_failure_returns_none(monkeypatch):
    install(monkeypatch, FakeCapture(frame=None))
    assert Camera().read() is None
