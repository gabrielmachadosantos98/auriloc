"""Snap waypoints drawn on the map to real streets, using an OSRM routing server.

The default server is the public OpenStreetMap one run by FOSSGIS, which offers car, bike
and foot profiles. It is meant for light use; for heavy use run your own OSRM and pass
its URL with `auriloc web --routing-url`.
"""

import asyncio
import json
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from auriloc.routes import LatLon

# `{profile}` becomes car, bike or foot. A self-hosted OSRM serves a single profile,
# so its URL usually has no placeholder: http://localhost:5000/route/v1/driving
DEFAULT_ROUTING_URL = "https://routing.openstreetmap.de/routed-{profile}/route/v1/driving"
MAX_WAYPOINTS = 100
TIMEOUT_S = 15.0
CACHE_SIZE = 32

try:
    USER_AGENT = f"auriloc/{version('auriloc')}"
except PackageNotFoundError:
    USER_AGENT = "auriloc"


class RoutingError(Exception):
    """The routing server could not produce a path along the streets."""


def build_url(base_url: str, profile: str, waypoints: Sequence[LatLon]) -> str:
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in waypoints)  # OSRM wants lon,lat
    query = urllib.parse.urlencode({"overview": "full", "geometries": "geojson", "steps": "false"})
    return f"{base_url.format(profile=profile).rstrip('/')}/{coords}?{query}"


def parse_response(data: dict[str, Any]) -> list[LatLon]:
    code = data.get("code")
    if code != "Ok":
        if code in ("NoRoute", "NoSegment"):
            raise RoutingError("No path along the streets connects these points. Try moving them onto a road.")
        raise RoutingError(f"The routing server refused the route: {data.get('message') or code}")
    try:
        coords = data["routes"][0]["geometry"]["coordinates"]
    except (KeyError, IndexError, TypeError) as e:
        raise RoutingError("The routing server sent an unexpected answer.") from e
    path = [(float(lat), float(lon)) for lon, lat in coords]
    if len(path) < 2:
        raise RoutingError("The routing server returned an empty path.")
    return path


def fetch_street_path(
    waypoints: Sequence[LatLon], profile: str, base_url: str = DEFAULT_ROUTING_URL, timeout: float = TIMEOUT_S
) -> list[LatLon]:
    """Path along the streets through `waypoints`, in order (blocking HTTP call)."""
    if len(waypoints) < 2:
        raise ValueError("A route needs at least 2 points.")
    if len(waypoints) > MAX_WAYPOINTS:
        raise ValueError(f"Following streets supports at most {MAX_WAYPOINTS} route points.")
    request = urllib.request.Request(
        build_url(base_url, profile, waypoints), headers={"User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except urllib.error.HTTPError as e:
        # OSRM answers errors such as NoRoute with a 400 and a JSON body.
        try:
            data = json.load(e)
        except Exception:
            raise RoutingError(f"The routing server answered HTTP {e.code}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise RoutingError(f"Could not reach the routing server ({reason}). Check the internet connection.") from e
    except json.JSONDecodeError as e:
        raise RoutingError("The routing server sent an unreadable answer.") from e
    return parse_response(data)


class StreetRouter:
    """Async wrapper with a small cache, so previewing a route and then starting it costs one request."""

    def __init__(self, base_url: str = DEFAULT_ROUTING_URL) -> None:
        self.base_url = base_url
        self._cache: OrderedDict[tuple[Any, ...], list[LatLon]] = OrderedDict()

    async def route(self, waypoints: Sequence[LatLon], profile: str) -> list[LatLon]:
        key = (profile, *((round(lat, 6), round(lon, 6)) for lat, lon in waypoints))
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        path = await asyncio.to_thread(fetch_street_path, waypoints, profile, self.base_url)
        self._cache[key] = path
        if len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return path
