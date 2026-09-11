"""Temporal hand identity and time-aware pointer filtering (no vision/GUI imports)."""

import itertools
import math
from dataclasses import dataclass, replace


def palm(hand):
    return tuple(sum(hand.points[i][axis] for i in (0, 5, 9, 13, 17)) / 5 for axis in (0, 1))


class SmoothPoint:
    """Adaptive low-pass: suppress slow jitter, increase cutoff during intentional motion."""

    def __init__(self, cutoff=1.5, beta=8.0):
        self.cutoff, self.beta = cutoff, beta
        self.value = self.raw = self.time = None
        self.velocity = (0.0, 0.0)

    @staticmethod
    def alpha(cutoff, dt):
        return 1 / (1 + 1 / (2 * math.pi * cutoff * dt))

    def update(self, point, now):
        if self.time is None or now - self.time > 0.3:
            self.value = self.raw = point
            self.time = now
            self.velocity = (0.0, 0.0)
            return point
        dt = max(0.001, min(0.1, now - self.time))
        a = self.alpha(1.0, dt)
        self.velocity = tuple(v + a * ((p - r) / dt - v) for p, r, v in zip(point, self.raw, self.velocity))
        cutoff = self.cutoff + self.beta * math.hypot(*self.velocity)
        a = self.alpha(cutoff, dt)
        self.value = tuple(v + a * (p - v) for p, v in zip(point, self.value))
        self.raw, self.time = point, now
        return self.value


@dataclass
class Track:
    ident: int
    hand: object
    center: tuple
    seen: float
    frames: int = 1
    votes: float = 0.0
    side: str | None = None
    velocity: tuple = (0.0, 0.0)
    label_confidence: float = 0.0


class HandTracker:
    """Associate by predicted palm position; lock anatomical label after acquisition.

    If two assignments are indistinguishable, output no hands and reacquire instead
    of transferring a held button to a different person/hand.
    """

    def __init__(self, swap=False, acquire_frames=3):
        self.swap = swap
        self.acquire_frames = acquire_frames
        self.tracks = []
        self.next_id = 1

    def reset(self):
        self.tracks.clear()

    def update(self, hands, now):
        hands = [
            h
            for h in hands
            if len(h.points) == 21
            and all(math.isfinite(v) and -0.2 <= v <= 1.2 for p in h.points for v in p)
            and h.distance(5, 17) > 0.025
        ]
        self.tracks = [t for t in self.tracks if now - t.seen < 0.25]
        if not hands:
            return []
        centers = [palm(h) for h in hands]
        matches = {}
        if self.tracks:
            costs = []
            # At most two hands/tracks; enumerate all injective assignments including unmatched.
            for assignment in itertools.product(range(-1, len(self.tracks)), repeat=len(hands)):
                used = [i for i in assignment if i >= 0]
                if len(set(used)) != len(used):
                    continue
                cost = 0.0
                for hi, ti in enumerate(assignment):
                    if ti < 0:
                        cost += 0.24
                        continue
                    t = self.tracks[ti]
                    dt = min(0.1, now - t.seen)
                    predicted = tuple(p + v * dt for p, v in zip(t.center, t.velocity))
                    distance = math.dist(centers[hi], predicted)
                    cost += distance if distance < 0.22 else 10.0
                costs.append((cost, assignment))
            costs.sort()
            if (
                len(hands) == 2
                and len(self.tracks) == 2
                and len(costs) > 1
                and costs[1][0] - costs[0][0] < 0.025
                and all(i >= 0 for i in costs[0][1])
            ):
                self.reset()
                return []
            matches = {hi: self.tracks[ti] for hi, ti in enumerate(costs[0][1]) if ti >= 0}
        observed = []
        for i, h in enumerate(hands):
            label = h.side
            if self.swap:
                label = "Left" if label == "Right" else "Right"
            vote = h.confidence * (1 if label == "Right" else -1)
            track = matches.get(i)
            if track is None:
                track = Track(self.next_id, h, centers[i], now, votes=vote)
                self.next_id += 1
                self.tracks.append(track)
            else:
                dt = max(0.01, now - track.seen)
                track.velocity = tuple(
                    max(-2, min(2, (p - old) / dt)) for p, old in zip(centers[i], track.center)
                )
                track.hand, track.center, track.seen = h, centers[i], now
                track.frames += 1
                if track.side is None:
                    track.votes += vote
            observed.append(track)
        for track in observed:
            if track.side is None and track.frames >= self.acquire_frames:
                candidate = "Right" if track.votes > 0 else "Left"
                if abs(track.votes) / track.frames >= 0.65 and not any(
                    t.side == candidate and t is not track for t in self.tracks
                ):
                    track.side = candidate
                    track.label_confidence = abs(track.votes) / track.frames
        # Retain the acquired label confidence; current category confidence is not pose confidence.
        return [
            replace(
                t.hand,
                side=t.side,
                confidence=t.label_confidence,
                track_id=t.ident,
            )
            for t in observed
            if t.side is not None
        ]
