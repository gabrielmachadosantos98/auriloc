import pytest

from auriloc.routes import haversine_m, interpolate_route, route_length_m

# Avenida Paulista, Sao Paulo: Consolacao -> Paraiso (~2.5 km in a straight line)
CONSOLACAO = (-23.5552, -46.6621)
PARAISO = (-23.5713, -46.6449)


def test_haversine_known_distance():
    # 1 degree of latitude ~ 111.2 km
    assert haversine_m((0.0, 0.0), (1.0, 0.0)) == pytest.approx(111_195, rel=1e-3)


def test_points_are_evenly_spaced_at_speed():
    speed_kmh, interval_s = 36.0, 1.0  # 10 m per step
    points = interpolate_route([CONSOLACAO, PARAISO], speed_kmh, interval_s)
    steps = [haversine_m(a, b) for a, b in zip(points, points[1:])]
    assert all(s == pytest.approx(10.0, abs=0.05) for s in steps[:-1])
    assert 0 < steps[-1] <= 10.05


def test_starts_and_ends_on_waypoints():
    points = interpolate_route([CONSOLACAO, PARAISO], 50.0)
    assert points[0] == CONSOLACAO
    assert points[-1] == pytest.approx(PARAISO)


def test_point_count_matches_duration():
    length = route_length_m([CONSOLACAO, PARAISO])
    points = interpolate_route([CONSOLACAO, PARAISO], 5.0, 1.0)
    expected_steps = length / (5.0 / 3.6)
    assert len(points) - 1 == pytest.approx(expected_steps, abs=1)


def test_step_carries_over_between_segments():
    # Three collinear waypoints: spacing must not "restart" in the middle of the route.
    middle = ((CONSOLACAO[0] + PARAISO[0]) / 2, (CONSOLACAO[1] + PARAISO[1]) / 2)
    one = interpolate_route([CONSOLACAO, PARAISO], 36.0)
    two = interpolate_route([CONSOLACAO, middle, PARAISO], 36.0)
    assert len(one) == len(two)


def test_duplicate_waypoints_are_harmless():
    points = interpolate_route([CONSOLACAO, CONSOLACAO, PARAISO], 36.0)
    assert points[-1] == pytest.approx(PARAISO)


@pytest.mark.parametrize(
    ("waypoints", "speed"),
    [([CONSOLACAO], 5.0), ([CONSOLACAO, PARAISO], 0.0), ([CONSOLACAO, PARAISO], -1.0)],
)
def test_invalid_input(waypoints, speed):
    with pytest.raises(ValueError):
        interpolate_route(waypoints, speed)
