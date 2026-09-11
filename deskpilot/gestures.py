"""Pure gesture state machine: no camera, Qt, or OS dependencies.

Every frame produces a finite list of actions. Only the desktop executor owns input.
Coordinates are normalized to the mirrored camera image, not a continuously moving mouse.
"""

import math
from dataclasses import dataclass, field

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


@dataclass
class Settings:
    dominant: str = "Right"
    pinch_on: float = 0.30
    pinch_off: float = 0.46
    smoothing: float = 0.40
    gain: float = 1.5
    zoom_step: float = 0.07
    min_confidence: float = 0.65
    dwell_seconds: float = 0.9


@dataclass
class GestureEngine:
    settings: Settings = field(default_factory=Settings)
    mode: str = "idle"
    latched: dict = field(default_factory=dict)
    previous: tuple | None = None
    zoom_anchor: float | None = None
    needs_open: bool = True

    def reset(self):
        self.mode = "idle"
        self.latched.clear()
        self.previous = None
        self.zoom_anchor = None
        self.needs_open = True
        return [Action("release")]

    def _pinches(self, hand):
        result = {}
        for tip in (8, 12, 16, 20):
            key = (hand.side, tip)
            threshold = self.settings.pinch_off if self.latched.get(key) else self.settings.pinch_on
            self.latched[key] = hand.ratio(tip) < threshold
            result[tip] = self.latched[key]
        return result

    def update(self, hands):
        # Ambiguous duplicate handedness must never transfer ownership mid-drag.
        valid = [h for h in hands if h.confidence >= self.settings.min_confidence]
        if len({h.side for h in valid}) != len(valid):
            return self.reset()
        primary = next((h for h in valid if h.side == self.settings.dominant), None)
        if primary is None:
            return self.reset()
        pins = {h.side: self._pinches(h) for h in valid}
        p = pins[primary.side]
        if sum(p.values()) > 1:
            return self.reset()
        if self.needs_open:
            if not any(any(v.values()) for v in pins.values()):
                self.needs_open = False
            return []
        secondary = next((h for h in valid if h.side != primary.side), None)
        zoom = secondary is not None and p[8] and pins[secondary.side][8]
        wanted = (
            "zoom"
            if zoom
            else next(
                (
                    name
                    for tip, name in ((20, "resize"), (16, "window"), (12, "click"), (8, "cursor"))
                    if p[tip]
                ),
                "idle",
            )
        )
        actions = []
        if wanted != self.mode:
            old = self.mode
            actions.append(Action("release"))
            self.mode = wanted
            self.previous = primary.points[8]
            self.zoom_anchor = None
            # Finish a gesture before changing its meaning. Prevent click after zoom/dropout.
            if old != "idle" and not (old == "cursor" and wanted == "zoom"):
                self.needs_open = True
                self.mode = "idle"
                return actions
            if wanted == "click":
                actions.append(Action("click_at", primary.points[8]))
            elif wanted in ("window", "resize"):
                actions.append(Action("begin_" + wanted, primary.points[8]))
        if wanted in ("cursor", "window", "resize"):
            current = primary.points[8]
            if self.previous is not None:
                dx = (current[0] - self.previous[0]) * self.settings.smoothing
                dy = (current[1] - self.previous[1]) * self.settings.smoothing
                self.previous = (self.previous[0] + dx, self.previous[1] + dy)
                if abs(dx) + abs(dy) > 0.00001:
                    actions.append(Action("move", (dx * self.settings.gain, dy * self.settings.gain)))
            else:
                self.previous = current
        elif wanted == "zoom":
            distance = math.dist(primary.points[8], secondary.points[8])
            if self.zoom_anchor is None:
                self.zoom_anchor = distance
            delta = distance - self.zoom_anchor
            steps = int(delta / self.settings.zoom_step)
            if steps:
                actions.append(Action("zoom", (max(-3, min(3, steps)),)))
                self.zoom_anchor = distance
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
