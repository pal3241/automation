import math
from dataclasses import replace

from test_gestures import hand

from deskpilot.tracking import HandTracker, SmoothPoint


def test_temporal_identity_ignores_intermittent_classifier_flip():
    t = HandTracker()
    for frame in range(3):
        result = t.update([hand(confidence=0.9)], frame / 30)
    assert len(result) == 1 and result[0].side == "Right"
    ident = result[0].track_id
    for frame in range(3, 12):
        result = t.update([hand("Left", dx=0.01 * (frame - 2), confidence=0.9)], frame / 30)
        assert result[0].side == "Right" and result[0].track_id == ident


def test_detection_list_reorder_preserves_identity():
    t = HandTracker()
    for frame in range(3):
        result = t.update([hand(dx=0.1), hand("Left", dx=-0.2)], frame / 30)
    ids = {h.side: h.track_id for h in result}
    result = t.update([hand("Right", dx=-0.19), hand("Left", dx=0.11)], 0.1)
    assert {h.side: h.track_id for h in result} == ids
    assert next(h for h in result if h.side == "Right").points[0][0] > 0.5


def test_ambiguous_crossing_is_dropped_not_swapped():
    t = HandTracker()
    for frame in range(3):
        t.update([hand(dx=0.1), hand("Left", dx=-0.1)], frame / 30)
    assert t.update([hand(), hand("Left")], 0.1) == []


def test_expired_track_gets_new_identity_and_swap_is_explicit():
    t = HandTracker(swap=True)
    for frame in range(3):
        result = t.update([hand()], frame / 30)
    assert result[0].side == "Left"
    previous = result[0].track_id
    assert t.update([], 1) == []
    for frame in range(3):
        result = t.update([hand()], 1.1 + frame / 30)
    assert result[0].track_id != previous


def test_invalid_landmarks_rejected():
    t = HandTracker()
    h = hand()
    points = list(h.points)
    points[0] = (float("nan"), 0)
    assert t.update([replace(h, points=tuple(points))], 0) == []


def test_filter_reduces_stationary_jitter_and_remains_responsive():
    f = SmoothPoint()
    output = [f.update((0.5 + 0.003 * (-1) ** i, 0.5), i / 60)[0] for i in range(120)]
    rms = math.sqrt(sum((v - 0.5) ** 2 for v in output[30:]) / 90)
    assert rms < 0.001
    for i in range(1, 16):
        result = f.update((0.7, 0.5), 2 + i / 60)
    assert abs(result[0] - 0.7) < 0.015


def test_filter_frame_rate_independent_for_equal_duration():
    outputs = []
    for fps in (20, 60):
        f = SmoothPoint()
        for frame in range(fps + 1):
            value = f.update((0.2 + 0.3 * frame / fps, 0.5), frame / fps)
        outputs.append(value[0])
    assert abs(outputs[0] - outputs[1]) < 0.01
