from dataclasses import replace

from deskpilot.gestures import Dwell, GestureEngine, Hand, Settings


def hand(side="Right", pinch=None, dx=0, confidence=1.0):
    points = [(0.5, 0.9)] * 21
    points[5], points[17] = (0.35, 0.65), (0.65, 0.65)
    points[4] = (0.15, 0.4)
    for index, tip in enumerate((8, 12, 16, 20)):
        points[tip] = (0.4 + index * 0.12, 0.25)
    if pinch:
        points[pinch] = (0.16, 0.4)
    return Hand(side, tuple((x + dx, y) for x, y in points), confidence)


def armed():
    engine = GestureEngine()
    engine.update([hand()])
    return engine


def kinds(actions):
    return [a.kind for a in actions]


def test_no_movement_with_open_hand():
    e = armed()
    assert e.update([hand(dx=0.2)]) == []


def test_clutch_preserves_pointer_on_grab_moves_and_releases():
    e = armed()
    assert "move" not in kinds(e.update([hand(pinch=8)]))
    assert "move" in kinds(e.update([hand(pinch=8, dx=0.1)]))
    assert kinds(e.update([hand(dx=0.2)])) == ["release"]
    assert "move" not in kinds(e.update([hand(dx=0.3)]))


def test_middle_click_once_per_pinch_at_index_tip():
    e = armed()
    h = hand(pinch=12)
    actions = e.update([h])
    assert actions[-1].kind == "click_at"
    assert actions[-1].values == h.points[8]
    for _ in range(20):
        assert "click_at" not in kinds(e.update([h]))
    e.update([hand()])
    e.update([hand()])
    assert "click_at" in kinds(e.update([h]))


def test_initial_closed_hand_does_not_activate():
    e = GestureEngine()
    assert e.update([hand(pinch=12)]) == []


def test_loss_releases_and_requires_open_hand():
    e = armed()
    e.update([hand(pinch=16)])
    assert kinds(e.update([])) == ["release"]
    assert e.update([hand(pinch=16)]) == []
    e.update([hand()])
    assert "begin_window" in kinds(e.update([hand(pinch=16)]))


def test_wrong_hand_does_not_take_over():
    e = armed()
    assert "click_at" not in kinds(e.update([hand("Left", 12)]))


def test_low_confidence_and_duplicate_handedness_release():
    e = armed()
    assert kinds(e.update([hand(confidence=0.4)])) == ["release"]
    assert kinds(e.update([hand(), hand()])) == ["release"]


def test_left_hand_configuration():
    e = GestureEngine(Settings(dominant="Left"))
    e.update([hand("Left")])
    assert "click_at" in kinds(e.update([hand("Left", 12)]))


def test_two_hand_zoom_can_start_after_cursor_grab():
    e = armed()
    e.update([hand(pinch=8), hand("Left", dx=0.3)])
    assert e.mode == "cursor"
    e.update([hand(pinch=8), hand("Left", pinch=8, dx=0.3)])
    assert e.mode == "zoom"
    actions = e.update([hand(pinch=8), hand("Left", pinch=8, dx=0.5)])
    assert actions[0].kind == "zoom" and actions[0].values[0] > 0
    assert "move" not in kinds(actions)
    assert kinds(e.update([hand(pinch=8)])) == ["release"]
    assert e.update([hand(pinch=8, dx=0.3)]) == []


def test_pinch_hysteresis():
    e = armed()
    e.update([hand(pinch=8)])
    h = hand(pinch=8)
    points = list(h.points)
    points[8] = (points[4][0] + 0.30 * 0.38, points[4][1])
    e.update([replace(h, points=tuple(points))])
    assert e.mode == "cursor"


def test_dwell_fires_once_until_exit():
    d = Dwell()
    assert not d.update("stop", 0, 0.9)[0]
    assert d.update("stop", 1, 0.9)[0]
    assert not d.update("stop", 2, 0.9)[0]
    d.update(None, 3, 0.9)
    assert not d.update("stop", 4, 0.9)[0]
    assert d.update("stop", 5, 0.9)[0]


def test_ambiguous_fist_does_not_trigger_resize():
    e = armed()
    h = hand(pinch=8)
    points = list(h.points)
    for tip in (12, 16, 20):
        points[tip] = points[8]
    assert kinds(e.update([replace(h, points=tuple(points))])) == ["release"]
    assert e.needs_open
