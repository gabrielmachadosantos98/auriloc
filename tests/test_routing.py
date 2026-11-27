import asyncio
import io
import json
import urllib.error

import pytest

from auriloc import routing
from auriloc.controller import Controller
from auriloc.motion import TravelMode
from auriloc.routing import RoutingError, StreetRouter, build_url, fetch_street_path, parse_response

A = (-23.5552, -46.6621)
B = (-23.5713, -46.6449)
OK = {"code": "Ok", "routes": [{"geometry": {"coordinates": [[-46.6621, -23.5552], [-46.65, -23.56], [-46.6449, -23.5713]]}}]}


def test_url_uses_lon_lat_order_and_profile():
    url = build_url(routing.DEFAULT_ROUTING_URL, "bike", [A, B])
    assert url.startswith("https://routing.openstreetmap.de/routed-bike/route/v1/driving/")
    assert "/-46.662100,-23.555200;-46.644900,-23.571300?" in url
    assert "geometries=geojson" in url and "overview=full" in url


def test_self_hosted_url_without_placeholder():
    url = build_url("http://localhost:5000/route/v1/driving/", "car", [A, B])
    assert url.startswith("http://localhost:5000/route/v1/driving/-46.662100,")


def test_parse_returns_lat_lon():
    assert parse_response(OK) == [A, (-23.56, -46.65), B]


@pytest.mark.parametrize("body", [{"code": "NoRoute"}, {"code": "InvalidQuery", "message": "bad"}, {"code": "Ok"}])
def test_parse_errors(body):
    with pytest.raises(RoutingError):
        parse_response(body)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_reads_osrm_answer(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"], seen["ua"] = request.full_url, request.get_header("User-agent")
        return _Response(json.dumps(OK).encode())

    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    assert fetch_street_path([A, B], "foot")[-1] == B
    assert "routed-foot" in seen["url"]
    assert seen["ua"].startswith("auriloc")


def test_fetch_turns_osrm_400_into_readable_error(monkeypatch):
    def fake_urlopen(request, timeout):
        body = io.BytesIO(json.dumps({"code": "NoRoute"}).encode())
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, body)

    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RoutingError, match="No path along the streets"):
        fetch_street_path([A, B], "car")


def test_fetch_offline(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.URLError("no network")

    monkeypatch.setattr(routing.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(RoutingError, match="Could not reach"):
        fetch_street_path([A, B], "car")


def test_too_many_waypoints():
    with pytest.raises(ValueError):
        fetch_street_path([A] * (routing.MAX_WAYPOINTS + 1), "car")


def test_router_caches(monkeypatch):
    calls = []

    def fake_fetch(waypoints, profile, base_url):
        calls.append(profile)
        return [A, B]

    monkeypatch.setattr(routing, "fetch_street_path", fake_fetch)
    router = StreetRouter()

    async def run():
        await router.route([A, B], "car")
        await router.route([A, B], "car")
        await router.route([A, B], "foot")

    asyncio.run(run())
    assert calls == ["car", "foot"]


class _FakeRouter:
    def __init__(self):
        self.profiles = []

    async def route(self, waypoints, profile):
        self.profiles.append(profile)
        return [waypoints[0], (-23.56, -46.65), waypoints[-1]]


def test_controller_plans_along_streets_with_mode_profile():
    router = _FakeRouter()
    controller = Controller(router=router)
    plan = asyncio.run(controller.plan_route([A, B], travel_mode=TravelMode.CYCLING, follow_streets=True))
    assert router.profiles == ["bike"]
    assert len(plan.path) == 3
    assert plan.speed_kmh == 18
    assert plan.points[-1] == pytest.approx(B)
    assert plan.summary()["travel_mode"] == "cycling"


def test_controller_without_streets_does_not_call_router():
    router = _FakeRouter()
    plan = asyncio.run(Controller(router=router).plan_route([A, B], 30, TravelMode.DRIVING))
    assert router.profiles == []
    assert plan.path == [A, B]
    assert plan.speed_kmh == 30


def test_controller_legacy_constant_speed():
    plan = asyncio.run(Controller(router=_FakeRouter()).plan_route([A, B], 36))
    assert plan.travel_mode is None


@pytest.mark.parametrize("kwargs", [{"follow_streets": True, "speed_kmh": 10}, {}])
def test_controller_rejects_incomplete_requests(kwargs):
    with pytest.raises(ValueError):
        asyncio.run(Controller(router=_FakeRouter()).plan_route([A, B], **kwargs))
