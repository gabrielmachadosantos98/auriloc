import random

import pytest

from auriloc.motion import PROFILES, TravelMode, plan_motion
from auriloc.routes import haversine_m, route_length_m

# Avenida Paulista, Sao Paulo: Consolacao -> Paraiso (~2.5 km in a straight line)
CONSOLACAO = (-23.5552, -46.6621)
PARAISO = (-23.5713, -46.6449)


def _speeds_kmh(points):
    return [haversine_m(a, b) * 3.6 for a, b in zip(points, points[1:])]


def _plan(path, mode, seed=1, **kw):
    return plan_motion(path, PROFILES[mode], rng=random.Random(seed), **kw)


def _corner():
    """Two 500 m legs meeting at a right angle (east, then north)."""
    lat, lon = CONSOLACAO
    dlat = 500 / 111_195
    dlon = 500 / (111_195 * 0.917)  # cos(-23.55 deg) ~ 0.917
    return [(lat, lon), (lat, lon + dlon), (lat + dlat, lon + dlon)]


@pytest.mark.parametrize("mode", list(TravelMode))
def test_starts_and_ends_on_the_path(mode):
    points = _plan([CONSOLACAO, PARAISO], mode)
    assert points[0] == pytest.approx(CONSOLACAO)
    assert points[-1] == pytest.approx(PARAISO)


@pytest.mark.parametrize("mode", list(TravelMode))
def test_starts_and_stops_at_rest(mode):
    cruise = PROFILES[mode].cruise_kmh
    speeds = _speeds_kmh(_plan([CONSOLACAO, PARAISO], mode))
    assert speeds[0] < cruise * 0.6
    assert speeds[-1] < cruise * 0.6


@pytest.mark.parametrize("mode", list(TravelMode))
def test_cruises_near_the_mode_speed(mode):
    cruise = PROFILES[mode].cruise_kmh
    speeds = _speeds_kmh(_plan([CONSOLACAO, PARAISO], mode))
    middle = speeds[len(speeds) // 4 : -len(speeds) // 4]
    assert all(cruise * 0.8 < s < cruise * 1.2 for s in middle)
    # Natural drift: not a robotic constant speed.
    assert max(middle) - min(middle) > cruise * 0.02


def test_acceleration_is_limited():
    profile = PROFILES[TravelMode.DRIVING]
    speeds_ms = [s / 3.6 for s in _speeds_kmh(_plan([CONSOLACAO, PARAISO], TravelMode.DRIVING))]
    changes = [b - a for a, b in zip(speeds_ms, speeds_ms[1:])]
    # Per-second averages, so allow a little slack over the per-instant limits.
    assert max(changes) <= profile.accel_ms2 * 1.1
    assert min(changes) >= -profile.decel_ms2 * 1.1


def test_car_slows_down_for_a_right_angle_turn():
    corner = _corner()
    points = _plan(corner, TravelMode.DRIVING)
    speeds = _speeds_kmh(points)
    # Slowest moment in the middle third of the trip is the corner, well below cruise.
    third = len(speeds) // 3
    assert min(speeds[third:-third]) < 25
    # And it happens near the corner vertex.
    slowest = third + speeds[third:-third].index(min(speeds[third:-third]))
    assert haversine_m(points[slowest], corner[1]) < 30


def test_walker_barely_slows_for_the_same_turn():
    speeds = _speeds_kmh(_plan(_corner(), TravelMode.WALKING))
    third = len(speeds) // 3
    assert min(speeds[third:-third]) > 4.0


def test_turning_takes_longer_than_going_straight():
    corner = _corner()
    straight_len = route_length_m(corner)
    lat, lon = CONSOLACAO
    straight = [(lat, lon), (lat, lon + straight_len / (111_195 * 0.917))]
    t_corner = len(_plan(corner, TravelMode.DRIVING))
    t_straight = len(_plan(straight, TravelMode.DRIVING))
    assert t_corner > t_straight


def test_cruise_speed_override():
    slow = _plan([CONSOLACAO, PARAISO], TravelMode.DRIVING, cruise_kmh=20)
    fast = _plan([CONSOLACAO, PARAISO], TravelMode.DRIVING, cruise_kmh=60)
    assert len(slow) > 2 * len(fast)


def test_same_seed_same_route():
    a = _plan([CONSOLACAO, PARAISO], TravelMode.CYCLING, seed=7)
    b = _plan([CONSOLACAO, PARAISO], TravelMode.CYCLING, seed=7)
    assert a == b


def test_u_turn_does_not_stall():
    lat, lon = CONSOLACAO
    out = (lat, lon + 0.002)
    points = _plan([CONSOLACAO, out, CONSOLACAO], TravelMode.DRIVING)
    assert points[-1] == pytest.approx(CONSOLACAO)
    assert len(points) < 200


def test_very_short_and_duplicate_paths():
    near = (CONSOLACAO[0] + 0.00002, CONSOLACAO[1])  # ~2 m away
    points = _plan([CONSOLACAO, CONSOLACAO, near], TravelMode.WALKING)
    assert points[-1] == pytest.approx(near)
    assert _plan([CONSOLACAO, CONSOLACAO], TravelMode.WALKING) == [CONSOLACAO]


@pytest.mark.parametrize(("path", "kw"), [([CONSOLACAO], {}), ([CONSOLACAO, PARAISO], {"cruise_kmh": 0})])
def test_invalid_input(path, kw):
    with pytest.raises(ValueError):
        plan_motion(path, PROFILES[TravelMode.WALKING], **kw)
