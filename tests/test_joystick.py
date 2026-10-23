from tv_air_remote.joystick import Direction, PalmJoystick, is_open_hand, palm_point


def feed(joy, frames, allowed=None):
    """frames: (t_ms, x, y). Restituisce [(t_ms, Direction)]."""
    out = []
    for t, x, y in frames:
        args = () if allowed is None else (allowed,)
        result = joy.update((x, y), t, *args)
        if result is not None:
            out.append((t, result))
    return out


def at(t0, t1, x, y, step=33):
    return [(t, x, y) for t in range(t0, t1 + 1, step)]


def centered(x=0.5, y=0.5, **kwargs):
    """Joystick con il centro già fissato in (x, y)."""
    joy = PalmJoystick(**kwargs)
    feed(joy, at(0, 330, x, y))
    assert joy.center == (x, y)
    return joy


def hand(open_fingers, wrist=(0.5, 0.5)):
    """21 landmark: dita distese (punta lontana dal polso) o piegate."""
    wx, wy = wrist
    points = [(wx, wy - 0.05)] * 21
    points[0] = wrist
    for tip, pip in ((8, 6), (12, 10), (16, 14), (20, 18)):
        points[pip] = (wx, wy - 0.10)
        points[tip] = (wx, wy - (0.20 if open_fingers else 0.06))
    return tuple(points)


def test_open_hand_from_landmarks():
    assert is_open_hand(hand(True))
    assert not is_open_hand(hand(False))
    assert not is_open_hand(())


def test_palm_point_is_mean_of_palm_landmarks():
    points = [(0.0, 0.0)] * 21
    for i, p in zip((0, 5, 9, 13, 17), ((0.4, 0.6), (0.5, 0.5), (0.6, 0.5), (0.6, 0.6), (0.4, 0.3))):
        points[i] = p
    assert palm_point(tuple(points), (0.4, 0.6)) == (0.5, 0.5)
    assert palm_point((), (0.3, 0.7)) == (0.3, 0.7)


def test_center_needs_still_palm():
    joy = PalmJoystick(arm_ms=300)
    feed(joy, at(0, 260, 0.5, 0.5))
    assert joy.center is None
    feed(joy, at(293, 330, 0.5, 0.5))
    assert joy.center == (0.5, 0.5)


def test_moving_palm_does_not_set_center():
    joy = PalmJoystick()
    feed(joy, [(t, 0.3 + t / 1000, 0.5) for t in range(0, 600, 33)])
    assert joy.center is None


def test_no_command_before_center():
    assert feed(PalmJoystick(), at(0, 100, 0.5, 0.5) + at(133, 400, 0.8, 0.5)) == []


def test_four_directions():
    for (x, y), expected in (((0.5, 0.3), Direction.UP), ((0.5, 0.7), Direction.DOWN),
                             ((0.3, 0.5), Direction.LEFT), ((0.7, 0.5), Direction.RIGHT)):
        assert feed(centered(), [(400, x, y)]) == [(400, expected)]


def test_small_movement_is_enough():
    # Basta spostare il palmo di poco più dell'8% (con la media serve un frame in più).
    assert feed(centered(), at(400, 500, 0.6, 0.5))[0][1] is Direction.RIGHT


def test_smoothing_ignores_single_frame_jitter():
    joy = centered()
    assert feed(joy, [(400, 0.62, 0.5), (433, 0.5, 0.5), (466, 0.5, 0.5)]) == []


def test_center_is_idle():
    assert feed(centered(), at(400, 2000, 0.52, 0.48)) == []


def test_repeat_is_slow_near_the_border():
    result = feed(centered(smoothing=1.0), at(400, 2000, 0.59, 0.5, step=10))
    times = [t for t, _ in result]
    assert len(times) >= 2
    assert all(b - a >= 600 for a, b in zip(times, times[1:]))


def test_repeat_is_fast_far_from_center():
    result = feed(centered(smoothing=1.0), at(400, 2000, 0.75, 0.5, step=10))
    times = [t for t, _ in result]
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert max(gaps) <= 160 and min(gaps) >= 150


def test_back_to_center_stops():
    joy = centered()
    feed(joy, at(400, 500, 0.7, 0.5))
    assert feed(joy, at(533, 2000, 0.5, 0.5)) == []
    assert joy.direction is None


def test_right_to_left_switches_without_pause():
    joy = centered(smoothing=1.0)
    assert feed(joy, [(400, 0.7, 0.5), (433, 0.5, 0.5), (466, 0.3, 0.5)]) == [
        (400, Direction.RIGHT), (466, Direction.LEFT)]


def test_jump_to_other_direction_without_idle():
    assert feed(centered(smoothing=1.0), [(400, 0.7, 0.5), (433, 0.5, 0.3)]) == [
        (400, Direction.RIGHT), (433, Direction.UP)]


def test_border_jitter_does_not_retrigger():
    # Tra idle (0.05) e zone (0.08) lo stato resta quello di prima.
    frames = [(400 + 33 * i, 0.5 + (0.06 if i % 2 else 0.07), 0.5) for i in range(8)]
    assert feed(centered(smoothing=1.0), frames) == []
    result = feed(centered(smoothing=1.0), [(400, 0.59, 0.5), (433, 0.56, 0.5), (466, 0.59, 0.5)])
    assert result == [(400, Direction.RIGHT)]


def test_disallowed_direction_is_idle():
    only_left = frozenset({Direction.LEFT, Direction.UP, Direction.DOWN})
    joy = centered(smoothing=1.0)
    assert feed(joy, at(400, 1500, 0.7, 0.5), only_left) == []
    assert feed(joy, [(1533, 0.3, 0.5)], only_left) == [(1533, Direction.LEFT)]


def test_reset_clears_center():
    joy = centered()
    joy.reset()
    assert joy.center is None
    assert feed(joy, [(400, 0.7, 0.5)]) == []


def test_latch_waits_for_idle_and_keeps_center():
    joy = centered(smoothing=1.0)
    feed(joy, [(400, 0.7, 0.5)])
    joy.latch()
    assert feed(joy, at(433, 1500, 0.7, 0.5)) == []  # nessuna ripetizione
    assert feed(joy, [(1533, 0.5, 0.5), (1566, 0.3, 0.5)]) == [(1566, Direction.LEFT)]
    assert joy.center == (0.5, 0.5)


def test_diagonal_does_not_flip_between_axes():
    # In diagonale dx e dy si equivalgono: l'asse resta quello iniziato.
    joy = centered(smoothing=1.0)
    frames = [(400, 0.62, 0.40)] + [
        (433 + 33 * i, 0.5 + (0.10 if i % 2 else 0.12), 0.5 - (0.12 if i % 2 else 0.10))
        for i in range(20)]
    assert {d for _, d in feed(joy, frames)} == {Direction.RIGHT}


def test_clear_change_of_axis_still_switches():
    joy = centered(smoothing=1.0)
    assert feed(joy, [(400, 0.62, 0.5), (433, 0.52, 0.35)]) == [
        (400, Direction.RIGHT), (433, Direction.UP)]


def test_latch_with_recenter_moves_center_where_palm_rests():
    joy = centered(smoothing=1.0)
    joy.latch(recenter=True)
    assert feed(joy, at(400, 800, 0.3, 0.5)) == []  # niente comando a sorpresa
    assert joy.center == (0.3, 0.5)
    assert feed(joy, [(833, 0.15, 0.5)]) == [(833, Direction.LEFT)]


def test_resting_in_border_band_does_not_repeat():
    joy = centered(smoothing=1.0)
    assert feed(joy, [(400, 0.6, 0.5)] + at(433, 3000, 0.56, 0.5)) == [(400, Direction.RIGHT)]


def thumb_hand(thumb_tip, wrist=(0.5, 0.6)):
    """Quattro dita piegate, pollice disteso con la punta in thumb_tip."""
    wx, wy = wrist
    points = [(wx, wy)] * 21
    for k, (mcp, pip, dip, tip) in enumerate(((5, 6, 7, 8), (9, 10, 11, 12),
                                              (13, 14, 15, 16), (17, 18, 19, 20))):
        x = wx - 0.05 + 0.04 * k
        points[mcp] = (x, wy - 0.10)
        points[pip] = (x, wy - 0.15)
        points[dip] = (x, wy - 0.11)
        points[tip] = (x, wy - 0.08)  # punta ripiegata verso il palmo
    points[1] = (wx - 0.05, wy - 0.03)
    points[2] = (wx - 0.08, wy - 0.05)
    points[3] = ((points[2][0] + thumb_tip[0]) / 2, (points[2][1] + thumb_tip[1]) / 2)
    points[4] = thumb_tip
    return tuple(points)


def test_thumb_left_from_landmarks():
    from tv_air_remote.joystick import is_thumb_left

    assert is_thumb_left(thumb_hand((0.30, 0.53)))
    assert not is_thumb_left(thumb_hand((0.58, 0.53)))   # pollice verso destra
    assert not is_thumb_left(thumb_hand((0.43, 0.38)))   # pollice su
    assert not is_thumb_left(thumb_hand((0.47, 0.52)))   # pugno
    assert not is_thumb_left(hand(True))                 # palmo aperto
    assert not is_thumb_left(())
