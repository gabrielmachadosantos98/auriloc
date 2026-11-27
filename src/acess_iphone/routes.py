"""Transforma waypoints desenhados no mapa em pontos espaçados no tempo, a uma velocidade constante."""

import math
from collections.abc import Sequence

LatLon = tuple[float, float]

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(a: LatLon, b: LatLon) -> float:
    """Distância em metros entre dois pontos (lat, lon) em graus."""
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def route_length_m(waypoints: Sequence[LatLon]) -> float:
    return sum(haversine_m(a, b) for a, b in zip(waypoints, waypoints[1:]))


def _lerp(a: LatLon, b: LatLon, f: float) -> LatLon:
    # Interpolação linear em graus: erro desprezível para trechos de algumas centenas de metros.
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def interpolate_route(waypoints: Sequence[LatLon], speed_kmh: float, interval_s: float = 1.0) -> list[LatLon]:
    """Pontos ao longo da rota, um a cada `interval_s` segundos, andando a `speed_kmh`.

    O primeiro ponto é o início da rota e o último é sempre o waypoint final, mesmo que o
    último passo seja mais curto que os outros.
    """
    if len(waypoints) < 2:
        raise ValueError("A rota precisa de pelo menos 2 pontos.")
    if speed_kmh <= 0:
        raise ValueError("A velocidade precisa ser maior que zero.")
    if interval_s <= 0:
        raise ValueError("O intervalo precisa ser maior que zero.")

    step_m = speed_kmh / 3.6 * interval_s
    points: list[LatLon] = [tuple(waypoints[0])]  # type: ignore[list-item]
    remaining = step_m  # quanto falta andar até emitir o próximo ponto
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
