"""Local web server with the map (`auriloc web`)."""

import asyncio
import logging
import socket
import webbrowser
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from auriloc.controller import Controller, describe_error
from auriloc.device import DeviceNotReadyError
from auriloc.motion import TravelMode
from auriloc.routing import DEFAULT_ROUTING_URL, RoutingError, StreetRouter

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    points: list[Point] = Field(min_length=2, max_length=5000)
    # Cruise speed. Optional when a travel mode is given (each mode has its own default).
    speed_kmh: Optional[float] = Field(default=None, gt=0, le=300)
    # walking | running | cycling | driving: moves like that mode (accelerates, slows in turns).
    # Omitted: straight lines at a constant speed, as before.
    travel_mode: Optional[TravelMode] = None
    # Follow real streets between the points (needs a travel mode and internet).
    follow_streets: bool = False

    @model_validator(mode="after")
    def _speed_or_mode(self) -> "RouteRequest":
        if self.speed_kmh is None and self.travel_mode is None:
            raise ValueError("Give speed_kmh or travel_mode.")
        if self.follow_streets and self.travel_mode is None:
            raise ValueError("follow_streets needs a travel_mode.")
        return self

    def args(self) -> tuple[Any, ...]:
        return ([(p.lat, p.lon) for p in self.points], self.speed_kmh, self.travel_mode, self.follow_streets)


async def _guard(call: Awaitable[Any], controller: Controller) -> dict[str, Any]:
    """Turn iPhone failures into HTTP responses with a readable message."""
    try:
        await call
    except DeviceNotReadyError as e:
        raise HTTPException(409, str(e)) from e
    except RoutingError as e:
        raise HTTPException(502, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        logger.exception("failed to talk to the iPhone")
        raise HTTPException(502, f"Failed to talk to the iPhone: {describe_error(e)}") from e
    return controller.status()


def create_app(udid: Optional[str] = None, routing_url: str = DEFAULT_ROUTING_URL) -> FastAPI:
    controller = Controller(udid, router=StreetRouter(routing_url))

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await controller.start()
        try:
            yield
        finally:
            # When the server stops, the iPhone goes back to real GPS.
            await controller.shutdown()

    app = FastAPI(title="Auriloc", lifespan=lifespan)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/status")
    async def status() -> dict[str, Any]:
        return controller.status()

    @app.post("/api/location")
    async def set_location(point: Point) -> dict[str, Any]:
        return await _guard(controller.set_point(point.lat, point.lon), controller)

    @app.post("/api/route/plan")
    async def plan_route(req: RouteRequest) -> dict[str, Any]:
        """Preview a route (path along the streets, distance, duration) without moving the iPhone."""
        try:
            plan = await controller.plan_route(*req.args())
        except RoutingError as e:
            raise HTTPException(502, str(e)) from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        return plan.summary()

    @app.post("/api/route")
    async def start_route(req: RouteRequest) -> dict[str, Any]:
        return await _guard(controller.start_route(*req.args()), controller)

    @app.post("/api/stop")
    async def stop_route() -> dict[str, Any]:
        return await _guard(controller.stop_route(), controller)

    @app.post("/api/clear")
    async def clear() -> dict[str, Any]:
        return await _guard(controller.clear(), controller)

    return app


LOOPBACK_HOSTS = ("127.0.0.1", "localhost")


class PortUnavailableError(RuntimeError):
    """The server could not listen on the requested port."""


def _bind(family: socket.AddressFamily, address: str, port: int) -> socket.socket:
    sock = socket.socket(family, socket.SOCK_STREAM)
    try:
        if family == socket.AF_INET6:
            sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1)
        # No SO_REUSEADDR: on Windows it would let another process take over the port.
        sock.bind((address, port))
    except BaseException:
        sock.close()
        raise
    return sock


def loopback_sockets(port: int) -> list[socket.socket]:
    """Listening sockets on both IPv4 and IPv6 loopback.

    Windows resolves `localhost` to ::1 first; with an IPv4-only server every request
    to `localhost` waited ~2 s for that attempt to fail before falling back to 127.0.0.1.
    """
    try:
        sockets = [_bind(socket.AF_INET, "127.0.0.1", port)]
    except OSError as e:
        raise PortUnavailableError(
            f"Port {port} is not available ({e.strerror or e}). "
            "Is Auriloc already running? Use --port to pick another one."
        ) from e
    if socket.has_ipv6:
        try:
            sockets.append(_bind(socket.AF_INET6, "::1", port))
        except OSError:
            logger.debug("IPv6 loopback unavailable; listening on IPv4 only", exc_info=True)
    return sockets


async def serve(
    host: str = "127.0.0.1",
    port: int = 8765,
    udid: Optional[str] = None,
    open_browser: bool = True,
    routing_url: str = DEFAULT_ROUTING_URL,
) -> None:
    config = uvicorn.Config(create_app(udid, routing_url), host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    sockets = loopback_sockets(port) if host in LOOPBACK_HOSTS else None
    url = f"http://{'localhost' if host in (*LOOPBACK_HOSTS, '0.0.0.0') else host}:{port}"
    print(f"Map at {url}  (Ctrl+C to stop and return to real GPS)")
    if open_browser:
        asyncio.get_running_loop().call_later(1.0, webbrowser.open, url)
    try:
        await server.serve(sockets=sockets)
    finally:
        for sock in sockets or []:
            sock.close()
