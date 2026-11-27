"""Turn waypoints drawn on the map into points evenly spaced in time, at a constant speed."""

import math
from collections.abc import Sequence

LatLon = tuple[float, float]

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(a: LatLon, b: LatLon) -> float:
    """Distance in meters between two (lat, lon) points in degrees."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def route_length_m(waypoints: Sequence[LatLon]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(waypoints, waypoints[1:]))


def _lerp(a: LatLon, b: LatLon, f: float) -> LatLon:
    # Linear interpolation in degrees: negligible error for segments of a few hundred meters.
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def interpolate_route(waypoints: Sequence[LatLon], speed_kmh: float, interval_s: float = 1.0) -> list[LatLon]:
    """Points along the route, one every `interval_s` seconds, moving at `speed_kmh`.

    The first point is the start of the route and the last one is always the final
    waypoint, even if that last step is shorter than the others.
    """
    if len(waypoints) < 2:
        raise ValueError("A route needs at least 2 points.")
    if speed_kmh <= 0:
        raise ValueError("Speed must be greater than zero.")
    if interval_s <= 0:
        raise ValueError("Interval must be greater than zero.")

    step_m = speed_kmh / 3.6 * interval_s
    points: list[LatLon] = [tuple(waypoints[0])]  # type: ignore[list-item]
    remaining = step_m  # distance left to travel before emitting the next point
    for a, b in zip(waypoints, waypoints[1:]):
        segment = haversine_m(a, b)
        travelled = 0.0
        while segment - travelled >= remaining:
            travelled += remaining
            points.append(_lerp(a, b, travelled / segment))
            remaining = step_m
        remaining -= segment - travelled

    end = tuple(waypoints[-1])
    if haversine_m(points[-1], end) > 0.01:  # type: ignore[arg-type]
        points.append(end)  # type: ignore[arg-type]
    return points
