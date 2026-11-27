"""Realistic movement along a path: per-mode speeds, acceleration, braking and slowing in turns.

`interpolate_route` (in `routes.py`) moves at one constant speed. This module plays a path
the way a person or vehicle would: it starts from a standstill, accelerates up to a cruise
speed that drifts naturally, slows down before turns (more for sharper ones) and brakes to
a stop at the end. Output is one point every `interval_s` seconds, like `interpolate_route`.
"""

import math
import random
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional

from auriloc.routes import LatLon, haversine_m

MIN_SPEED_MS = 0.5  # floor for turn speed, so a U-turn never stalls the route
MAX_STEP_M = 5.0  # path is split into pieces of at most this length before planning speeds
TURN_SPAN_CAP_M = 15.0  # how much of each side of a corner is used to estimate its radius


class TravelMode(StrEnum):
    WALKING = "walking"
    RUNNING = "running"
    CYCLING = "cycling"
    DRIVING = "driving"


@dataclass(frozen=True)
class MotionProfile:
    cruise_kmh: float  # typical speed on a straight stretch
    accel_ms2: float  # how fast it speeds up
    decel_ms2: float  # how hard it brakes
    lateral_ms2: float  # sideways acceleration tolerated in a turn (lower = slower turns)
    variation: float  # natural drift of the cruise speed, as a fraction (0.1 = +/-10%)
    street_profile: str  # routing profile used to follow streets: car, bike or foot


PROFILES: dict[TravelMode, MotionProfile] = {
    TravelMode.WALKING: MotionProfile(5.0, 0.5, 0.8, 1.0, 0.06, "foot"),
    TravelMode.RUNNING: MotionProfile(10.0, 1.0, 1.2, 2.0, 0.08, "foot"),
    TravelMode.CYCLING: MotionProfile(18.0, 0.8, 1.5, 2.0, 0.10, "bike"),
    TravelMode.DRIVING: MotionProfile(40.0, 2.0, 3.0, 2.5, 0.12, "car"),
}


def _dedupe(path: Sequence[LatLon]) -> list[LatLon]:
    out: list[LatLon] = [tuple(path[0])]  # type: ignore[list-item]
    for p in path[1:]:
        if haversine_m(out[-1], p) > 0.01:
            out.append(tuple(p))  # type: ignore[arg-type]
    return out


def _turn_angle(a: LatLon, b: LatLon, c: LatLon) -> float:
    """Heading change at `b` in radians: 0 = straight on, pi = U-turn."""
    # Local flat projection around b (meters); plenty precise for neighbouring vertices.
    k = math.cos(math.radians(b[0]))
    v1 = ((b[1] - a[1]) * k, b[0] - a[0])
    v2 = ((c[1] - b[1]) * k, c[0] - b[0])
    n1, n2 = math.hypot(*v1), math.hypot(*v2)
    if n1 == 0 or n2 == 0:
        return 0.0
    cos = max(-1.0, min(1.0, (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)))
    return math.acos(cos)


def _turn_speed_caps(path: list[LatLon], profile: MotionProfile) -> list[float]:
    """Highest comfortable speed (m/s) at each vertex, from the turn there (v = sqrt(a * r))."""
    caps = [math.inf] * len(path)
    for i in range(1, len(path) - 1):
        theta = _turn_angle(path[i - 1], path[i], path[i + 1])
        if theta < 1e-3:
            continue
        span = min(haversine_m(path[i - 1], path[i]), haversine_m(path[i], path[i + 1]), TURN_SPAN_CAP_M)
        radius = span / (2 * math.tan(theta / 2)) if theta < math.pi - 1e-6 else 0.0
        caps[i] = max(MIN_SPEED_MS, math.sqrt(profile.lateral_ms2 * radius))
    return caps


def _densify(path: list[LatLon], caps: list[float]) -> tuple[list[LatLon], list[float], list[float]]:
    """Split segments longer than MAX_STEP_M. Returns nodes, their turn caps and segment lengths."""
    total = sum(haversine_m(a, b) for a, b in zip(path, path[1:]))
    # At least 2 pieces, so a short route still has a moving middle between start and stop.
    max_step = min(MAX_STEP_M, total / 2)
    nodes, node_caps, lengths = [path[0]], [caps[0]], []
    for i, (a, b) in enumerate(zip(path, path[1:])):
        seg = haversine_m(a, b)
        pieces = max(1, math.ceil(seg / max_step))
        for j in range(1, pieces + 1):
            f = j / pieces
            nodes.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            node_caps.append(caps[i + 1] if j == pieces else math.inf)
            lengths.append(seg / pieces)
    return nodes, node_caps, lengths


def _drift(distances: list[float], amplitude: float, rng: random.Random) -> list[float]:
    """Smooth speed multiplier around 1.0, varying over hundreds of meters (never per step)."""
    waves = [(rng.uniform(120, 250), rng.uniform(0, 2 * math.pi)),
             (rng.uniform(300, 600), rng.uniform(0, 2 * math.pi)),
             (rng.uniform(700, 1500), rng.uniform(0, 2 * math.pi))]
    out = []
    for s in distances:
        wave = sum(math.sin(2 * math.pi * s / length + phase) for length, phase in waves) / len(waves)
        out.append(1.0 + amplitude * wave)
    return out


def plan_motion(
    path: Sequence[LatLon],
    profile: MotionProfile,
    interval_s: float = 1.0,
    cruise_kmh: Optional[float] = None,
    rng: Optional[random.Random] = None,
) -> list[LatLon]:
    """Points along `path`, one every `interval_s` seconds, moving like `profile`.

    Starts and ends at rest. `cruise_kmh` overrides the profile's cruise speed; `rng` makes
    the natural speed drift reproducible (tests pass a seeded one).
    """
    if len(path) < 2:
        raise ValueError("A route needs at least 2 points.")
    if interval_s <= 0:
        raise ValueError("Interval must be greater than zero.")
    cruise_ms = (cruise_kmh if cruise_kmh is not None else profile.cruise_kmh) / 3.6
    if cruise_ms <= 0:
        raise ValueError("Speed must be greater than zero.")

    clean = _dedupe(path)
    if len(clean) < 2:
        return [clean[0]]

    nodes, caps, lengths = _densify(clean, _turn_speed_caps(clean, profile))
    distances = [0.0]
    for ds in lengths:
        distances.append(distances[-1] + ds)
    drift = _drift(distances, profile.variation, rng or random.Random())
    limit = [min(cap, cruise_ms * d) for cap, d in zip(caps, drift)]

    # Speed at each node: start and end at rest; forward pass limits acceleration,
    # backward pass limits braking (so it slows *before* a turn, not inside it).
    n = len(nodes)
    v = [0.0] * n
    for i in range(1, n):
        v[i] = min(limit[i], math.sqrt(v[i - 1] ** 2 + 2 * profile.accel_ms2 * lengths[i - 1]))
    v[-1] = 0.0
    for i in range(n - 2, -1, -1):
        v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2 * profile.decel_ms2 * lengths[i]))
    v[0] = 0.0

    # Time to cross each piece, at constant acceleration between its two node speeds.
    times = [0.0]
    for i, ds in enumerate(lengths):
        times.append(times[-1] + 2 * ds / (v[i] + v[i + 1]))

    points: list[LatLon] = [nodes[0]]
    seg = 0
    k = 1
    while k * interval_s < times[-1]:
        t = k * interval_s
        while times[seg + 1] < t:
            seg += 1
        dt = t - times[seg]
        ds, v0, v1 = lengths[seg], v[seg], v[seg + 1]
        accel = (v1 * v1 - v0 * v0) / (2 * ds)
        f = min(1.0, (v0 * dt + 0.5 * accel * dt * dt) / ds)
        a, b = nodes[seg], nodes[seg + 1]
        points.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
        k += 1
    points.append(nodes[-1])
    return points
