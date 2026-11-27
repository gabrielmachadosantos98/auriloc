"""Local web server with the map (`auriloc web`)."""

import asyncio
import logging
import webbrowser
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auriloc.controller import Controller, describe_error
from auriloc.device import DeviceNotReadyError

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"


class Point(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class RouteRequest(BaseModel):
    points: list[Point] = Field(min_length=2, max_length=5000)
    speed_kmh: float = Field(gt=0, le=300)


async def _guard(call: Awaitable[None], controller: Controller) -> dict[str, Any]:
    """Turn iPhone failures into HTTP responses with a readable message."""
    try:
        await call
    except DeviceNotReadyError as e:
        raise HTTPException(409, str(e)) from e
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    except Exception as e:
        logger.exception("failed to talk to the iPhone")
        raise HTTPException(502, f"Failed to talk to the iPhone: {describe_error(e)}") from e
    return controller.status()


def create_app(udid: Optional[str] = None) -> FastAPI:
    controller = Controller(udid)

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

    @app.post("/api/route")
    async def start_route(req: RouteRequest) -> dict[str, Any]:
        waypoints = [(p.lat, p.lon) for p in req.points]
        return await _guard(controller.start_route(waypoints, req.speed_kmh), controller)

    @app.post("/api/stop")
    async def stop_route() -> dict[str, Any]:
        return await _guard(controller.stop_route(), controller)

    @app.post("/api/clear")
    async def clear() -> dict[str, Any]:
        return await _guard(controller.clear(), controller)

    return app


async def serve(host: str = "127.0.0.1", port: int = 8765, udid: Optional[str] = None, open_browser: bool = True) -> None:
    config = uvicorn.Config(create_app(udid), host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    url = f"http://{'localhost' if host in ('127.0.0.1', '0.0.0.0') else host}:{port}"
    print(f"Map at {url}  (Ctrl+C to stop and return to real GPS)")
    if open_browser:
        asyncio.get_running_loop().call_later(1.0, webbrowser.open, url)
    await server.serve()
