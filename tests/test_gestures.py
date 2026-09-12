from dataclasses import replace

from deskpilot.gestures import Dwell, GestureEngine, Hand, Settings


def hand(side="Right", pinch=None, dx=0, confidence=1.0):
    points = [(0.5, 0.9)] * 21
    points[5], points[17] = (0.35, 0.65), (0.65, 0.65)
    points[4] = (0.15, 0.4)
    for index, tip in enumerate((8, 12, 16, 20)):
        points[tip] = (0.4 + index * 0.12, 0.25)
    for tip in (pinch,) if isinstance(pinch, int) else pinch or ():
        points[tip] = (0.16, 0.4)
    return Hand(side, tuple((x + dx, y) for x, y in points), confidence)


def armed(**kwargs):
    engine = GestureEngine(Settings(debounce=0, **kwargs))
    engine.update([hand(), hand("Left", dx=-0.2)], 0)
    return engine


def kinds(actions):
    return [a.kind for a in actions]


def test_open_hand_motion_leaves_both_cursors_stationary():
    e = armed()
    before = e.cursors
    assert e.update([hand(dx=0.2)], 0.03) == []
    assert e.cursors == before


def test_cursor_clutch_and_release():
    e = armed()
    before = e.cursors["Right"]
    e.update([hand(pinch=8)], 0.03)
    assert e.cursors["Right"] == before
    assert "pointer_at" in kinds(e.update([hand(pinch=8, dx=0.1)], 0.06))
    assert kinds(e.update([hand(dx=0.2)], 0.09)) == ["release"]
    before = e.cursors["Right"]
    e.update([hand(dx=0.3)], 0.12)
    assert e.cursors["Right"] == before


def test_left_click_is_one_down_and_release_without_repeat():
    e = armed()
    assert kinds(e.update([hand(pinch=12)], 0.03)) == ["left_down_at"]
    assert e.update([hand(pinch=12)], 0.06) == []
    assert kinds(e.update([hand()], 0.09)) == ["release"]
    assert kinds(e.update([hand(pinch=12)], 0.12)) == ["left_down_at"]


def test_drag_upgrade_keeps_same_button_down_and_no_jump():
    e = armed()
    e.update([hand(pinch=12)], 0.03)
    before = e.cursors["Right"]
    assert e.update([hand(pinch=(8, 12))], 0.06) == []
    assert e.cursors["Right"] == before
    actions = e.update([hand(pinch=(8, 12), dx=0.1)], 0.09)
    assert kinds(actions) == ["pointer_at"]
    assert e.update([hand(pinch=12)], 0.12) == []
    assert kinds(e.update([hand()], 0.15)) == ["release"]


def test_simultaneous_three_finger_drag_starts_one_press():
    e = armed()
    assert kinds(e.update([hand(pinch=(8, 12))], 0.03)) == ["left_down_at"]


def test_ring_is_right_click_once():
    e = armed()
    assert kinds(e.update([hand(pinch=16)], 0.03)) == ["right_click_at"]
    assert e.update([hand(pinch=16)], 0.06) == []


def test_pinky_window_or_resize_configurable():
    for mode in ("window", "resize"):
        e = armed(pinky_action=mode)
        assert kinds(e.update([hand(pinch=20)], 0.03)) == ["begin_" + mode]


def test_two_hand_pinch_resizes_outward_and_inward_without_double_press():
    for independent in (False, True):
        e = armed(independent=independent)
        start = e.update([hand(pinch=20), hand("Left", pinch=20, dx=-0.2)], 0.03)
        assert kinds(start)[-1] == "begin_resize"
        assert e.mode == "resize dua tangan"
        assert start[-1].side == ("Right" if independent else None)
        outward = e.update([hand(pinch=20, dx=0.1), hand("Left", pinch=20, dx=-0.3)], 0.06)
        assert kinds(outward) == ["pointer_at"]
        assert outward[0].values[0] > start[-1].values[0]
        inward = e.update([hand(pinch=20, dx=-0.05), hand("Left", pinch=20, dx=-0.15)], 0.09)
        assert kinds(inward) == ["pointer_at"]
        assert inward[0].values[0] < outward[0].values[0]
        assert kinds(e.update([hand(), hand("Left", pinch=20, dx=-0.15)], 0.12))[-1] == "release"
        assert e.update([hand(pinch=20), hand("Left", pinch=20, dx=-0.2)], 0.15) == []


def test_pair_requires_both_hands_in_same_view():
    e = armed()
    different = replace(hand("Left", pinch=20), camera_id=1)
    assert "begin_resize" not in kinds(e.update([hand(pinch=20), different], 0.03))
    e.update([hand(), replace(hand("Left"), camera_id=1)], 0.06)
    assert "begin_resize" in kinds(e.update([hand(pinch=20), hand("Left", pinch=20)], 0.09))
    assert "release" in kinds(e.update([hand(pinch=20), replace(hand("Left", pinch=20), camera_id=1)], 0.12))


def test_fingertip_mode_grabs_window_at_tip_and_releases_on_open():
    e = armed(fingertip_window=True)
    first = hand(pinch=8)
    actions = e.update([first], 0.03)
    assert kinds(actions) == ["begin_window"]
    assert actions[0].values == first.points[8]
    actions = e.update([hand(pinch=8, dx=0.1)], 0.06)
    assert kinds(actions) == ["pointer_at"]
    assert actions[0].values[0] > first.points[8][0]
    assert kinds(e.update([hand()], 0.09)) == ["release"]


def test_fingertip_mode_does_not_start_unknown_combination():
    e = armed(fingertip_window=True)
    assert "begin_window" not in kinds(e.update([hand(pinch=(8, 12))], 0.03))


def test_two_independent_cursors_with_locked_mouse_owner():
    e = armed()
    e.update([hand(pinch=8), hand("Left", pinch=8, dx=-0.2)], 0.03)
    before = e.cursors
    e.update([hand(pinch=8, dx=0.1), hand("Left", pinch=8, dx=-0.3)], 0.06)
    assert e.cursors["Right"][0] > before["Right"][0]
    assert e.cursors["Left"][0] < before["Left"][0]
    assert e.owner == "Right"
    e.update([hand(), hand("Left", pinch=8, dx=-0.3)], 0.09)
    assert e.owner is None  # blocked hand must open first, never steal on owner release
    e.update([hand(), hand("Left", dx=-0.3)], 0.12)
    e.update([hand(), hand("Left", pinch=8, dx=-0.3)], 0.15)
    assert e.owner == "Left"


def test_other_hand_cannot_click_or_steal_active_drag():
    e = armed()
    e.update([hand(pinch=(8, 12)), hand("Left", dx=-0.2)], 0.03)
    assert "right_click_at" not in kinds(e.update([hand(pinch=(8, 12)), hand("Left", pinch=16)], 0.06))
    assert e.owner == "Right"


def test_loss_and_reacquisition_require_open_hand():
    e = armed()
    e.update([hand(pinch=(8, 12))], 0.03)
    assert kinds(e.update([], 0.06)) == ["release"]
    assert e.update([hand(pinch=(8, 12))], 0.09) == []
    e.update([hand()], 0.12)
    assert "left_down_at" in kinds(e.update([hand(pinch=(8, 12))], 0.15))


def test_identity_change_low_confidence_and_duplicates_release():
    for replacement in ([replace(hand(pinch=12), track_id=9)], [hand(confidence=0.3)], [hand(), hand()]):
        e = armed()
        e.update([hand(pinch=12)], 0.03)
        assert "release" in kinds(e.update(replacement, 0.06))
        assert e.owner is None


def test_short_noise_does_not_click():
    e = GestureEngine(Settings(debounce=0.055))
    e.update([hand()], 0)
    assert e.update([hand(pinch=12)], 0.01) == []
    assert e.update([hand()], 0.04) == []
    e.update([hand(pinch=12)], 0.1)
    assert kinds(e.update([hand(pinch=12)], 0.16)) == ["left_down_at"]
    assert kinds(e.update([hand()], 0.17)) == ["release"]


def test_fist_releases_without_right_click():
    e = armed()
    e.update([hand(pinch=12)], 0.03)
    assert kinds(e.update([hand(pinch=(8, 12, 16, 20))], 0.06)) == ["release"]


def test_zoom_is_explicit_and_finishes_with_rearm():
    e = armed(two_hand_zoom=True)
    e.update([hand(pinch=8), hand("Left", pinch=8, dx=-0.2)], 0.03)
    assert e.mode == "zoom"
    assert "zoom" in kinds(e.update([hand(pinch=8, dx=0.1), hand("Left", pinch=8, dx=-0.3)], 0.06))
    assert kinds(e.update([hand(pinch=8)], 0.09)) == ["release"]
    assert e.update([hand(pinch=8)], 0.12) == []


def test_dwell_fires_once_until_exit():
    d = Dwell()
    assert not d.update("stop", 0, 0.9)[0]
    assert d.update("stop", 1, 0.9)[0]
    assert not d.update("stop", 2, 0.9)[0]
    d.update(None, 3, 0.9)
    assert not d.update("stop", 4, 0.9)[0]
    assert d.update("stop", 5, 0.9)[0]
