from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from io import BytesIO

import pytest
from test_gestures import hand

from deskpilot.gestures import GestureEngine, Settings
from deskpilot.multicamera import MultiCameraFusion, parse_camera_ids


def test_camera_list_validated_without_duplication():
    assert parse_camera_ids(" 0, 2,1 ") == (0, 2, 1)
    for value in ("", "0,", "0,0", "x", "21", ",1", "0,-1", ",".join(map(str, range(9)))):
        with pytest.raises(ValueError):
            parse_camera_ids(value)


def test_same_physical_hand_is_selected_once_from_multiple_cameras():
    fusion = MultiCameraFusion((0, 1))
    selected = fusion.select({0: [replace(hand(), track_id=1)], 1: [replace(hand(), track_id=4)]})
    assert len(selected) == 1
    assert selected[0].camera_id == 0 and selected[0].track_id == (0, 1)


def test_fallback_changes_identity_and_requires_rearm():
    fusion = MultiCameraFusion((0, 1))
    first = fusion.select({0: [replace(hand(), track_id=1)], 1: [replace(hand(), track_id=1)]})
    second = fusion.select({1: [replace(hand(), track_id=1)]})
    assert first[0].track_id != second[0].track_id
    assert second[0].camera_id == 1
    assert fusion.select({}) == []
    assert fusion.source == {}


def test_switch_view_drops_existing_click_and_rearms():
    fusion = MultiCameraFusion((0, 1))
    engine = GestureEngine(Settings(debounce=0))
    engine.update(fusion.select({0: [hand()], 1: [hand()]}), 0)
    pressed = engine.update(fusion.select({0: [hand(pinch=12)], 1: [hand(pinch=12)]}), 0.1)
    assert [a.kind for a in pressed] == ["left_down_at"]
    switched = engine.update(fusion.select({1: [hand(pinch=12)]}), 0.2)
    assert "release" in [a.kind for a in switched]
    assert engine.update(fusion.select({1: [hand(pinch=12)]}), 0.3) == []
    engine.update(fusion.select({1: [hand()]}), 0.4)
    assert [a.kind for a in engine.update(fusion.select({1: [hand(pinch=12)]}), 0.5)] == [
        "left_down_at"
    ]


def test_shared_camera_preferred_for_two_hand_resize():
    fusion = MultiCameraFusion((0, 1))
    fusion.select({0: [hand()], 1: [hand("Left")]})
    hands = fusion.select({0: [hand(), hand("Left")], 1: [hand(), hand("Left")]})
    assert len(hands) == 2
    assert {h.camera_id for h in hands} == {0}


def test_parallel_camera_start_downloads_model_once(monkeypatch, tmp_path):
    from deskpilot.camera import ensure_model

    calls = []

    def fake_urlopen(url, timeout):
        calls.append(url)
        return BytesIO(b"x" * 2048)

    monkeypatch.setattr("deskpilot.camera.urllib.request.urlopen", fake_urlopen)
    model = tmp_path / "hand.task"
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(ensure_model, (model, model, model)))
    assert results == [model] * 3
    assert len(calls) == 1 and model.stat().st_size == 2048
