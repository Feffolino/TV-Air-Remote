import pytest

from tv_air_remote.swipe import Direction, SwipeDetector


def feed(detector, frames):
    """frames: (t_ms, gesture, x, y). Restituisce [(t_ms, Direction)]."""
    out = []
    for t, gesture, x, y in frames:
        result = detector.update(gesture, (x, y), t)
        if result is not None:
            out.append((t, result))
    return out


def still(t0, t1, x, y, gesture="Open_Palm", step=33):
    return [(t, gesture, x, y) for t in range(t0, t1 + 1, step)]


def move(t0, start, end, duration, gesture="Open_Palm", steps=6):
    (x0, y0), (x1, y1) = start, end
    return [
        (t0 + duration * i // steps, gesture,
         x0 + (x1 - x0) * i / steps, y0 + (y1 - y0) * i / steps)
        for i in range(1, steps + 1)
    ]


@pytest.mark.parametrize("start,end,expected", [
    ((0.5, 0.6), (0.5, 0.3), Direction.UP),
    ((0.5, 0.4), (0.5, 0.7), Direction.DOWN),
    ((0.6, 0.5), (0.3, 0.5), Direction.LEFT),
    ((0.4, 0.5), (0.7, 0.5), Direction.RIGHT),
])
def test_swipe_directions(start, end, expected):
    frames = still(0, 330, *start) + move(363, start, end, 200)
    result = feed(SwipeDetector(), frames)
    assert [d for _, d in result] == [expected]


def test_swipe_needs_still_palm_first():
    frames = still(0, 200, 0.5, 0.6) + move(233, (0.5, 0.6), (0.5, 0.3), 200)
    assert feed(SwipeDetector(), frames) == []


def test_swipe_needs_open_palm():
    frames = (still(0, 330, 0.5, 0.6, gesture="Closed_Fist")
              + move(363, (0.5, 0.6), (0.5, 0.3), 200, gesture="Closed_Fist"))
    assert feed(SwipeDetector(), frames) == []


def test_short_movement_is_ignored():
    frames = still(0, 330, 0.5, 0.6) + move(363, (0.5, 0.6), (0.5, 0.45), 200)
    assert feed(SwipeDetector(), frames) == []


def test_slow_movement_is_ignored():
    frames = still(0, 330, 0.5, 0.6) + move(363, (0.5, 0.6), (0.5, 0.3), 800)
    assert feed(SwipeDetector(), frames) == []


def test_label_may_change_during_motion():
    frames = still(0, 330, 0.5, 0.6) + move(363, (0.5, 0.6), (0.5, 0.3), 200, gesture=None)
    assert [d for _, d in feed(SwipeDetector(), frames)] == [Direction.UP]


def test_one_swipe_per_movement():
    frames = (still(0, 330, 0.5, 0.6)
              + move(363, (0.5, 0.6), (0.5, 0.3), 200)
              + move(596, (0.5, 0.3), (0.5, 0.0), 200))
    assert len(feed(SwipeDetector(), frames)) == 1


def test_reset_disarms():
    detector = SwipeDetector()
    feed(detector, still(0, 330, 0.5, 0.6))
    assert detector.armed
    detector.reset()
    assert not detector.armed
    assert feed(detector, move(363, (0.5, 0.6), (0.5, 0.3), 200)) == []
