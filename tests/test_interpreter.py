from tests.test_joystick import hand
from tv_air_remote.config import parse_config
from tv_air_remote.interpreter import GestureInterpreter
from tv_air_remote.observation import HandObservation

CENTER = (0.5, 0.5)
OTHER = (0.2, 0.5)  # seconda mano, ferma, per la modalità Navigazione


def make(mapping=None, **thresholds):
    data = {"thresholds": thresholds}
    if mapping is not None:
        data["mapping"] = mapping
    return GestureInterpreter(parse_config(data, require_host=False))


def obs(gesture, t, wrist=CENTER, score=0.9, landmarks=()):
    return HandObservation(gesture, score, wrist, t, landmarks)


def run(interp, frames):
    """frames: (t_ms, [HandObservation, ...]). Restituisce [(t_ms, tasto)]."""
    sent = []
    for t, hands in frames:
        sent += [(t, key) for key in interp.update(hands, t)]
    return sent


def hold(gesture, t0, t1, step=33, wrist=CENTER, score=0.9, second=None, other=OTHER):
    """Una mano con la gesture; ``second``: gesture di una seconda mano in ``other``."""
    frames = []
    for t in range(t0, t1 + 1, step):
        hands = [obs(gesture, t, wrist, score)]
        if second is not None:
            hands.append(obs(second, t, other, 0.6))
        frames.append((t, hands))
    return frames


def gone(t0, t1, step=33):
    return [(t, []) for t in range(t0, t1 + 1, step)]


def keys(sent):
    return [key for _, key in sent]


def palm_to(t0, target, second=None, center=CENTER, until=None, other=OTHER):
    """Palmo fermo al centro per 400 ms, poi spostato su target fino a until."""
    frames = hold("Open_Palm", t0, t0 + 400, wrist=center, second=second, other=other)
    frames += hold("Open_Palm", t0 + 433, until or t0 + 433, wrist=target, second=second, other=other)
    return frames


def two_palms(t0, t1, left=(0.3, 0.5), right=(0.7, 0.5), step=33):
    return [(t, [obs("Open_Palm", t, left), obs("Open_Palm", t, right)])
            for t in range(t0, t1 + 1, step)]


def enter_nav(interp, t0=0):
    run(interp, hold("Closed_Fist", t0, t0 + 500, second="Closed_Fist", score=0.3))
    assert interp.mode == "nav"


# --- gesture statiche -------------------------------------------------------

def test_gesture_needs_five_stable_frames():
    assert run(make(), hold("Thumb_Up", 0, 99)) == []
    assert keys(run(make(), hold("Thumb_Up", 0, 132))) == ["KEY_VOLUP"]


def test_low_confidence_is_ignored():
    assert run(make(), hold("Thumb_Up", 0, 1000, score=0.5)) == []


def test_victory_is_not_play_pause_by_default():
    # MediaPipe la riconosce poco: in modalità TV pausa/play è il clic (OK).
    assert run(make(), hold("Victory", 0, 1500)) == []


def test_play_pause_action_alternates():
    interp = make(mapping={"tv": {"Victory": "PLAY_PAUSE"}})
    sent = run(interp, hold("Victory", 0, 300) + gone(333, 1200) + hold("Victory", 1233, 1500))
    assert keys(sent) == ["KEY_PAUSE", "KEY_PLAY"]


def test_single_command_while_held():
    assert keys(run(make(), hold("Closed_Fist", 0, 3000))) == ["KEY_HOME"]


def test_brief_label_loss_does_not_repeat_command():
    # Il pugno tenuto chiuso: MediaPipe perde l'etichetta per 200 ms, poi torna.
    frames = (hold("Closed_Fist", 0, 1200) + hold(None, 1233, 1400, score=0.2)
              + hold("Closed_Fist", 1433, 3000))
    assert keys(run(make(), frames)) == ["KEY_HOME"]


def test_command_again_after_release():
    frames = hold("Closed_Fist", 0, 1200) + gone(1233, 2000) + hold("Closed_Fist", 2033, 3200)
    assert keys(run(make(), frames)) == ["KEY_HOME", "KEY_HOME"]


def test_fist_needs_long_hold_for_home():
    assert run(make(), hold("Closed_Fist", 0, 900, step=10)) == []
    assert run(make(), hold("Closed_Fist", 0, 1100, step=10)) == [(1000, "KEY_HOME")]


def test_volume_repeats_and_accelerates():
    sent = run(make(), hold("Thumb_Up", 0, 3000, step=10))
    times = [t for t, _ in sent]
    assert set(keys(sent)) == {"KEY_VOLUP"}
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert gaps[0] == 300 and gaps[-1] == 150


def test_volume_stops_when_hand_is_lost():
    sent = run(make(), hold("Thumb_Up", 0, 500, step=10) + gone(510, 2000, step=10))
    assert all(t <= 500 for t, _ in sent)


def test_power_requires_long_hold():
    assert run(make(), hold("ILoveYou", 0, 1400, step=10)) == []
    assert run(make(), hold("ILoveYou", 0, 1600, step=10)) == [(1500, "KEY_POWER")]


def test_open_palm_alone_does_nothing():
    assert run(make(), hold("Open_Palm", 0, 3000)) == []


# --- modalità per numero di mani -------------------------------------------

def test_two_hands_switch_to_navigation_and_back():
    interp = make()
    run(interp, hold("Closed_Fist", 0, 300, second="Closed_Fist", score=0.3))
    assert interp.mode == "tv"  # serve nav_enter_ms di conteggio stabile
    run(interp, hold("Closed_Fist", 333, 500, second="Closed_Fist", score=0.3))
    assert interp.mode == "nav"
    run(interp, hold("Closed_Fist", 533, 1900, score=0.3))
    assert interp.mode == "nav"  # per uscire serve nav_exit_ms con una mano
    run(interp, hold("Closed_Fist", 1933, 2100, score=0.3))
    assert interp.mode == "tv"


def test_second_hand_lost_for_a_second_keeps_navigation():
    # MediaPipe perde spesso una delle due mani per qualche centinaio di ms.
    interp = make()
    enter_nav(interp)
    run(interp, hold("Closed_Fist", 533, 1500, score=0.3))
    run(interp, hold("Closed_Fist", 1533, 2500, second="Closed_Fist", score=0.3))
    run(interp, hold("Closed_Fist", 2533, 3500, score=0.3))
    assert interp.mode == "nav"


def test_no_hands_keep_mode():
    interp = make()
    enter_nav(interp)
    run(interp, gone(533, 3000))
    assert interp.mode == "nav"


def test_navigation_mapping():
    interp = make()
    enter_nav(interp)
    sent = run(interp, hold("Thumb_Up", 600, 900, second="Pointing_Up"))
    sent += run(interp, gone(933, 1500) + hold("Victory", 1533, 1800, second="Pointing_Up"))
    sent += run(interp, gone(1833, 2400) + hold("Thumb_Down", 2433, 2600, second="Pointing_Up"))
    sent += run(interp, gone(2633, 3200) + hold("Closed_Fist", 3233, 4500, second="Pointing_Up"))
    assert keys(sent) == ["KEY_ENTER", "KEY_RETURN", "KEY_VOLDOWN"]


def test_thumb_up_enter_does_not_repeat():
    interp = make()
    enter_nav(interp)
    assert keys(run(interp, hold("Thumb_Up", 600, 3000, step=10, second="Pointing_Up"))) == ["KEY_ENTER"]


# --- palmo come joystick ----------------------------------------------------

def test_palm_in_tv_mode_volume_and_channel():
    # Su/giù = volume, sinistra/destra = canale.
    assert keys(run(make(), palm_to(0, (0.5, 0.3)))) == ["KEY_VOLUP"]
    assert keys(run(make(), palm_to(0, (0.5, 0.7)))) == ["KEY_VOLDOWN"]
    assert keys(run(make(), palm_to(0, (0.7, 0.5)))) == ["KEY_CHUP"]
    assert keys(run(make(), palm_to(0, (0.3, 0.5)))) == ["KEY_CHDOWN"]


def test_palm_held_up_keeps_raising_volume():
    sent = keys(run(make(), palm_to(0, (0.5, 0.3), until=2000)))
    assert len(sent) >= 4 and set(sent) == {"KEY_VOLUP"}


def test_palm_arrows_in_navigation():
    # L'altra mano sta dal lato opposto alla direzione: la mano che si muove
    # è quella che può spingere verso quel lato.
    for target, key, other in (((0.5, 0.3), "KEY_UP", OTHER), ((0.5, 0.7), "KEY_DOWN", OTHER),
                               ((0.3, 0.5), "KEY_LEFT", (0.8, 0.5)), ((0.7, 0.5), "KEY_RIGHT", OTHER)):
        interp = make()
        enter_nav(interp)
        assert keys(run(interp, palm_to(600, target, second="Pointing_Up", other=other))) == [key]


def test_palm_held_repeats_arrow():
    interp = make()
    enter_nav(interp)
    sent = keys(run(interp, palm_to(600, (0.7, 0.5), second="Pointing_Up", until=2500)))
    assert sent[0] == "KEY_RIGHT" and len(sent) >= 4 and set(sent) == {"KEY_RIGHT"}


def test_palm_shape_without_label_drives_joystick():
    # MediaPipe a volte classifica il palmo aperto come "nessuna gesture".
    interp = make()
    frames = []
    for t, wrist in [(t, CENTER) for t in range(0, 401, 33)] + [(433, (0.5, 0.3))]:
        frames.append((t, [obs(None, t, wrist, 0.85, hand(True, wrist))]))
    assert keys(run(interp, frames)) == ["KEY_VOLUP"]


def test_mode_switch_keeps_center_but_waits_for_idle():
    interp = make()
    run(interp, palm_to(0, (0.5, 0.3)))  # volume + in modalità TV, palmo ancora su
    run(interp, hold("Open_Palm", 466, 1000, wrist=(0.5, 0.3), second="Pointing_Up"))
    assert interp.mode == "nav"
    # Il palmo era già spostato: nessuna freccia finché non torna al centro...
    assert run(interp, hold("Open_Palm", 1033, 1500, wrist=(0.5, 0.3), second="Pointing_Up")) == []
    # ...poi il joystick riprende subito, senza dover fissare un nuovo centro.
    frames = hold("Open_Palm", 1533, 1700, second="Pointing_Up")
    frames += hold("Open_Palm", 1733, 1800, wrist=(0.7, 0.5), second="Pointing_Up")
    assert keys(run(interp, frames)) == ["KEY_RIGHT"]


# --- due mani divise in Navigazione ----------------------------------------

def test_left_hand_goes_left_right_hand_goes_right():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    assert interp.mode == "nav"
    sent = run(interp, two_palms(833, 833, left=(0.2, 0.5)))
    sent += run(interp, two_palms(866, 1000))
    sent += run(interp, two_palms(1033, 1033, right=(0.8, 0.5)))
    assert keys(sent) == ["KEY_LEFT", "KEY_RIGHT"]


def test_inward_movement_is_ignored():
    # La mano sinistra verso destra e la destra verso sinistra: nessun comando.
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    assert run(interp, two_palms(833, 2000, left=(0.4, 0.5), right=(0.6, 0.5))) == []


def test_up_with_both_hands_sends_once():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    sent = run(interp, two_palms(833, 3000, step=10, left=(0.3, 0.35), right=(0.7, 0.35)))
    times = [t for t, _ in sent]
    assert set(keys(sent)) == {"KEY_UP"}
    assert len(set(times)) == len(times)  # mai due tasti nello stesso frame
    assert all(b - a >= 370 for a, b in zip(times, times[1:]))  # ritmo di una mano sola


def test_single_hand_in_navigation_does_every_direction():
    # MediaPipe perde una mano: per nav_exit_ms si resta in Navigazione e la
    # mano rimasta fa anche la direzione che di solito spetta all'altra.
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    run(interp, hold("Open_Palm", 833, 1300, wrist=(0.7, 0.5)))
    assert interp.mode == "nav"
    assert keys(run(interp, hold("Open_Palm", 1333, 1333, wrist=(0.6, 0.5)))) == ["KEY_LEFT"]


# --- clic: chiudi e riapri la mano = OK -------------------------------------

def click(t0, wrist=CENTER, fist_frames=3, other=None):
    """Palmo, pugno per fist_frames frame, di nuovo palmo."""
    frames = []
    for i, gesture in enumerate(["Open_Palm"] + ["Closed_Fist"] * fist_frames + ["Open_Palm"] * 2):
        t = t0 + 33 * i
        hands = [obs(gesture, t, wrist)]
        if other is not None:
            hands.append(obs("Open_Palm", t, other))
        frames.append((t, hands))
    return frames


def test_click_is_ok_in_tv_mode():
    interp = make()
    run(interp, hold("Open_Palm", 0, 400))
    assert keys(run(interp, click(433))) == ["KEY_ENTER"]


def test_click_is_ok_in_navigation_with_either_hand():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    assert interp.mode == "nav"
    assert keys(run(interp, click(833, wrist=(0.7, 0.5), other=(0.3, 0.5)))) == ["KEY_ENTER"]


def test_single_frame_fist_is_not_a_click():
    interp = make()
    run(interp, hold("Open_Palm", 0, 400))
    assert run(interp, click(433, fist_frames=1)) == []


def test_long_fist_is_not_a_click_and_still_opens_home():
    interp = make()
    run(interp, hold("Open_Palm", 0, 400))
    sent = run(interp, hold("Closed_Fist", 433, 1600, step=10) + hold("Open_Palm", 1610, 1700))
    assert keys(sent) == ["KEY_HOME"]


def test_click_keeps_joystick_center():
    interp = make(palm_smoothing=1.0)
    run(interp, hold("Open_Palm", 0, 400))
    run(interp, click(433))
    assert keys(run(interp, hold("Open_Palm", 700, 700, wrist=(0.7, 0.5)))) == ["KEY_CHUP"]


# --- passaggio da una mano all'altra ---------------------------------------

def test_hand_lost_briefly_keeps_its_center():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    # La webcam perde la mano sinistra per 600 ms, poi la ritrova dov'era.
    run(interp, hold("Open_Palm", 833, 1433, wrist=(0.7, 0.5)))
    sent = run(interp, two_palms(1466, 1500))
    sent += run(interp, two_palms(1533, 1533, left=(0.2, 0.5)))
    assert keys(sent) == ["KEY_LEFT"]


def test_returning_hand_off_center_recenters_when_still():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    run(interp, hold("Open_Palm", 833, 1433, wrist=(0.7, 0.5)))
    # Torna più a sinistra di prima: niente comando a sorpresa...
    assert run(interp, two_palms(1466, 1800, left=(0.15, 0.5))) == []
    # ...ma ferma lì diventa il nuovo centro e risponde subito.
    assert keys(run(interp, two_palms(1833, 1833, left=(0.05, 0.5)))) == ["KEY_LEFT"]


def test_resting_hand_slightly_up_does_not_block_the_other():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    sent = run(interp, two_palms(833, 833, right=(0.7, 0.38)))           # destra: su
    sent += run(interp, two_palms(866, 1500, right=(0.7, 0.44)))         # resta appena su
    sent += run(interp, two_palms(1533, 1533, left=(0.3, 0.62), right=(0.7, 0.44)))  # sinistra: giù
    assert keys(sent) == ["KEY_UP", "KEY_DOWN"]


def test_source_hand_is_reported():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    run(interp, two_palms(833, 833, left=(0.2, 0.5)))
    assert interp.last_source == "left"


# --- pollice a sinistra = indietro -----------------------------------------

def thumb_left_frames(t0, t1, label="Closed_Fist", wrist=(0.5, 0.6), other=None, step=33):
    from tests.test_joystick import thumb_hand

    frames = []
    for t in range(t0, t1 + 1, step):
        hands = [obs(label, t, wrist, 0.8, thumb_hand((wrist[0] - 0.2, wrist[1] - 0.07), wrist))]
        if other is not None:
            hands.append(obs("Open_Palm", t, other))
        frames.append((t, hands))
    return frames


def test_thumb_left_is_back_in_navigation():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    # MediaPipe lo scambia per un pugno: vale comunque come pollice a sinistra.
    sent = run(interp, thumb_left_frames(833, 3000, other=(0.3, 0.5), wrist=(0.75, 0.6)))
    assert keys(sent) == ["KEY_RETURN"]


def test_thumb_left_after_palm_is_not_a_click():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    frames = thumb_left_frames(833, 933, other=(0.3, 0.5), wrist=(0.75, 0.6))
    frames += two_palms(966, 1100, right=(0.75, 0.6))
    assert "KEY_ENTER" not in keys(run(interp, frames))


def test_thumb_left_does_nothing_in_tv_mode():
    assert run(make(), thumb_left_frames(0, 2000)) == []


def test_source_is_cleared_for_gestures():
    interp = make(palm_smoothing=1.0)
    run(interp, two_palms(0, 800))
    run(interp, two_palms(833, 833, left=(0.2, 0.5)))
    run(interp, thumb_left_frames(866, 2000, other=(0.3, 0.5), wrist=(0.75, 0.6)))
    assert interp.last_source is None
