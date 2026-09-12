"""Pure gesture state machine: no camera, Qt, or OS dependencies.

Every frame produces a finite list of actions. Only the desktop executor owns input.
Coordinates are normalized to the mirrored camera image, not a continuously moving mouse.
"""

import math
import time
from dataclasses import dataclass, field

from .tracking import SmoothPoint, palm

FINGERS = {4: "Ibu jari", 8: "Telunjuk", 12: "Tengah", 16: "Manis", 20: "Kelingking"}
CONNECTIONS = tuple(
    (a, b)
    for chain in (
        (0, 1, 2, 3, 4),
        (0, 5, 6, 7, 8),
        (5, 9, 10, 11, 12),
        (9, 13, 14, 15, 16),
        (13, 17, 18, 19, 20),
        (0, 17),
    )
    for a, b in zip(chain, chain[1:])
)


@dataclass(frozen=True)
class Hand:
    side: str
    points: tuple[tuple[float, float], ...]
    confidence: float = 1.0
    aspect: float = 4 / 3
    track_id: int = 0
    camera_id: int = 0

    def distance(self, a, b):
        p, q = self.points[a], self.points[b]
        return math.hypot((p[0] - q[0]) * self.aspect, p[1] - q[1])

    def ratio(self, tip):
        return self.distance(4, tip) / max(self.distance(5, 17), 0.025)

    def extended(self):
        return [
            name for tip, name in FINGERS.items() if self.distance(0, tip) > self.distance(0, tip - 2) * 1.13
        ]


@dataclass(frozen=True)
class Action:
    kind: str
    values: tuple = ()
    side: str | None = None


@dataclass
class Settings:
    dominant: str = "Right"  # tie-breaker only: both hands are enabled
    pinch_on: float = 0.30
    pinch_off: float = 0.46
    gain: float = 1.5
    min_cutoff: float = 1.5
    debounce: float = 0.055
    zoom_step: float = 0.07
    min_confidence: float = 0.65
    dwell_seconds: float = 0.9
    two_hand_zoom: bool = False
    pinky_action: str = "window"
    independent: bool = False
    fingertip_window: bool = False


@dataclass
class HandState:
    cursor: tuple | None = None
    mode: str = "idle"
    needs_open: bool = True
    pinches: dict = field(default_factory=dict)
    candidate: str = "idle"
    since: float = 0.0
    previous: tuple | None = None
    filter: object = None
    track_id: int = -1
    blocked: bool = False


class GestureEngine:
    def __init__(self, settings=None):
        self.settings = settings or Settings()
        self.states = {side: HandState() for side in ("Right", "Left")}
        self.owner = None
        self.mode = "idle"
        self.zoom_anchor = None
        self.resize_anchor = None

    @property
    def cursors(self):
        return {side: state.cursor for side, state in self.states.items() if state.cursor is not None}

    def reset_hand(self, side):
        old = self.states[side]
        self.states[side] = HandState(cursor=old.cursor, track_id=old.track_id)
        if self.settings.independent and old.mode != "idle":
            return [Action("release", side=side)]
        if self.owner == side:
            self.owner = None
            return [Action("release")]
        return []

    def reset(self):
        for side in self.states:
            self.reset_hand(side)
        self.owner = None
        self.mode = "idle"
        self.zoom_anchor = None
        self.resize_anchor = None
        return [Action("release")]

    @staticmethod
    def hand_span(a, b):
        pa, pb = palm(a), palm(b)
        aspect = (a.aspect + b.aspect) / 2
        return math.hypot((pa[0] - pb[0]) * aspect, pa[1] - pb[1])

    def wanted(self, hand, state):
        for tip in (8, 12, 16, 20):
            threshold = self.settings.pinch_off if state.pinches.get(tip) else self.settings.pinch_on
            state.pinches[tip] = hand.ratio(tip) < threshold
        fingers = {tip for tip, closed in state.pinches.items() if closed}
        return {
            frozenset(): "idle",
            frozenset({8}): "window_tip" if self.settings.fingertip_window else "cursor",
            frozenset({12}): "left",
            frozenset({8, 12}): "drag",
            frozenset({16}): "right",
            frozenset({20}): self.settings.pinky_action,
        }.get(frozenset(fingers), "invalid")

    def update(self, hands, now=None):
        now = time.monotonic() if now is None else now
        hands = [h for h in hands if h.confidence >= self.settings.min_confidence]
        if len({h.side for h in hands}) != len(hands):
            return self.reset()
        observed = {h.side: h for h in hands}
        actions = []
        for side in self.states:
            if side not in observed:
                actions.extend(self.reset_hand(side))
        desired = {}
        for side, hand in observed.items():
            state = self.states[side]
            if state.track_id != hand.track_id:
                actions.extend(self.reset_hand(side))
                state = self.states[side]
                state.track_id = hand.track_id
            if state.cursor is None:
                state.cursor = tuple(max(0, min(1, p)) for p in hand.points[8])
            raw = self.wanted(hand, state)
            if raw == "invalid":
                actions.extend(self.reset_hand(side))
                continue
            if state.needs_open:
                if raw == "idle":
                    state.needs_open = False
                continue
            if raw != state.candidate:
                state.candidate, state.since = raw, now
            # Releases are immediate; activation needs stable evidence in time, not frame count.
            if raw == "idle":
                desired[side] = raw
            elif now - state.since >= self.settings.debounce:
                desired[side] = raw
            else:
                desired[side] = state.mode
                # Button-up on loss of middle contact is never delayed by a new candidate.
                if state.mode in ("left", "drag") and not state.pinches[12]:
                    desired[side] = "idle"
        zoom = (
            not self.settings.independent
            and self.settings.two_hand_zoom
            and len(desired) == 2
            and all(v == "cursor" for v in desired.values())
        )
        if zoom:
            if self.zoom_anchor is None:
                actions.append(Action("release"))
                self.owner = None
                self.zoom_anchor = math.dist(palm(observed["Right"]), palm(observed["Left"]))
            distance = math.dist(palm(observed["Right"]), palm(observed["Left"]))
            steps = int((distance - self.zoom_anchor) / self.settings.zoom_step)
            if steps:
                actions.append(Action("zoom", (max(-3, min(3, steps)),)))
                self.zoom_anchor = distance
            self.mode = "zoom"
            return actions
        if self.zoom_anchor is not None:
            return self.reset()
        pinky_pair = (
            len(desired) == 2
            and all(self.states[s].pinches.get(20) for s in ("Right", "Left"))
            and all(desired[s] in ("window", "resize", "pair_resize") for s in ("Right", "Left"))
        )
        same_camera = pinky_pair and observed["Right"].camera_id == observed["Left"].camera_id
        if self.resize_anchor is not None:
            distance, side, start_cursor, track_ids, camera_id, last_delta = self.resize_anchor
            if not same_camera or tuple(observed[s].track_id for s in ("Right", "Left")) != track_ids:
                return self.reset()
            delta = self.hand_span(observed["Right"], observed["Left"]) - distance
            if abs(delta - last_delta) >= 0.006:
                position = tuple(max(0, min(1, axis + delta * self.settings.gain)) for axis in start_cursor)
                self.states[side].cursor = position
                actions.append(Action("pointer_at", position, side if self.settings.independent else None))
                self.resize_anchor = (distance, side, start_cursor, track_ids, camera_id, delta)
            self.mode = "resize dua tangan"
            return actions
        if pinky_pair and not same_camera:
            return self.reset()
        if same_camera:
            side = self.owner or self.settings.dominant
            start_cursor = self.states[side].cursor
            if start_cursor is None:
                return self.reset()
            # End a pending one-handed window drag before starting paired resize.
            actions.append(Action("release"))
            self.owner = None
            for state in self.states.values():
                state.mode = "pair_resize"
                state.previous = state.filter = None
            self.resize_anchor = (
                self.hand_span(observed["Right"], observed["Left"]),
                side,
                start_cursor,
                tuple(observed[s].track_id for s in ("Right", "Left")),
                observed[side].camera_id,
                0.0,
            )
            actions.append(Action("begin_resize", start_cursor, side if self.settings.independent else None))
            self.mode = "resize dua tangan"
            return actions
        # Existing owner first. A newly arriving hand cannot steal a held click/drag.
        order = sorted(desired, key=lambda side: (side != self.owner, side != self.settings.dominant))
        for side in order:
            state, hand = self.states[side], observed[side]
            wanted, old = desired[side], state.mode
            if wanted == "idle":
                if self.settings.independent and old != "idle":
                    actions.append(Action("release", side=side))
                elif self.owner == side:
                    actions.append(Action("release"))
                    self.owner = None
                state.mode, state.blocked = "idle", False
                state.previous = state.filter = None
                continue
            legal = (
                old == "idle"
                or old == wanted
                or {old, wanted} <= {"left", "drag"}
                or old == "cursor"
                and wanted in ("left", "drag")
            )
            if not legal:
                actions.extend(self.reset_hand(side))
                continue
            entering = old != wanted
            if old == "idle":
                state.blocked = not self.settings.independent and self.owner is not None and self.owner != side
                if not state.blocked and not self.settings.independent:
                    self.owner = side
            state.mode = wanted
            owns = (self.settings.independent or self.owner == side) and not state.blocked
            if entering:
                state.filter = SmoothPoint(self.settings.min_cutoff)
                if wanted == "window_tip":
                    state.cursor = tuple(max(0, min(1, v)) for v in hand.points[8])
                state.previous = state.filter.update(
                    hand.points[8] if wanted == "window_tip" else palm(hand), now
                )
                if owns:
                    if wanted in ("left", "drag") and old not in ("left", "drag"):
                        actions.append(Action("left_down_at", state.cursor, side if self.settings.independent else None))
                    elif wanted == "right":
                        actions.append(Action("right_click_at", state.cursor, side if self.settings.independent else None))
                    elif wanted in ("window", "resize", "window_tip"):
                        kind = "window" if wanted == "window_tip" else wanted
                        actions.append(Action("begin_" + kind, state.cursor, side if self.settings.independent else None))
                    elif wanted == "cursor":
                        actions.append(Action("pointer_at", state.cursor, side if self.settings.independent else None))
            if wanted in ("cursor", "drag", "window", "resize", "window_tip"):
                point = state.filter.update(hand.points[8] if wanted == "window_tip" else palm(hand), now)
                if math.dist(point, state.previous) >= 0.0007:
                    if wanted == "window_tip":
                        state.cursor = tuple(max(0, min(1, v)) for v in point)
                    else:
                        delta = tuple((p - q) * self.settings.gain for p, q in zip(point, state.previous))
                        state.cursor = tuple(max(0, min(1, p + d)) for p, d in zip(state.cursor, delta))
                    state.previous = point
                    if owns:
                        actions.append(Action("pointer_at", state.cursor, side if self.settings.independent else None))
        self.mode = " / ".join(f"{s}: {v.mode}" for s, v in self.states.items() if v.mode != "idle") or "idle"
        return actions


@dataclass
class Dwell:
    """One activation per entry. A hand must leave the button to rearm."""

    target: str | None = None
    since: float = 0.0
    fired: bool = False

    def update(self, target, now, duration):
        if target != self.target:
            self.target, self.since, self.fired = target, now, False
        progress = min(1.0, (now - self.since) / max(duration, 0.1)) if target else 0.0
        fire = bool(target and progress >= 1 and not self.fired)
        if fire:
            self.fired = True
        return fire, progress
