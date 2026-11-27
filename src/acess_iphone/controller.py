"""Estado da simulação para o servidor web.

Mantém uma única `LocationSession` aberta (o túnel userspace é um por processo), reconecta
sozinho se o iPhone for desconectado e reconectado, e reproduz rotas em segundo plano.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import asdict
from typing import Any, Literal, Optional, TypeVar

from acess_iphone.device import DeviceInfo, DeviceNotReadyError, ensure_ready
from acess_iphone.location import LocationSession, validate_coordinates
from acess_iphone.routes import LatLon, interpolate_route, route_length_m

logger = logging.getLogger(__name__)

T = TypeVar("T")
Mode = Literal["idle", "fixed", "route"]


def describe_error(error: BaseException) -> str:
    return str(error) or type(error).__name__


class Controller:
    def __init__(self, udid: Optional[str] = None, interval_s: float = 1.0) -> None:
        self.udid = udid
        self.interval_s = interval_s
        self.device: Optional[DeviceInfo] = None
        self.mode: Mode = "idle"
        self.current: Optional[LatLon] = None
        self.route: Optional[list[LatLon]] = None
        self.progress: Optional[tuple[int, int]] = None
        self.speed_kmh: Optional[float] = None
        self.error: Optional[str] = None
        self.connecting = False
        self._session: Optional[LocationSession] = None
        self._lock = asyncio.Lock()
        self._route_task: Optional[asyncio.Task[None]] = None
        self._route_stop: Optional[asyncio.Event] = None
        self._connect_task: Optional[asyncio.Task[None]] = None

    # ---- ciclo de vida ----------------------------------------------------------------

    async def start(self) -> None:
        """Conecta em segundo plano, para o servidor subir mesmo sem iPhone conectado."""
        self._connect_task = asyncio.create_task(self._initial_connect())

    async def _initial_connect(self) -> None:
        try:
            async with self._lock:
                await self._connect()
        except Exception as e:
            self.error = describe_error(e)
            logger.warning("não foi possível conectar ao iPhone: %s", self.error)

    async def shutdown(self) -> None:
        if self._connect_task is not None and not self._connect_task.done():
            self._connect_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._connect_task
        await self._cancel_route()
        async with self._lock:
            if self._session is not None and self.mode != "idle":
                with suppress(Exception):
                    await self._session.clear()
            await self._disconnect()

    # ---- conexão ----------------------------------------------------------------------

    async def _connect(self) -> LocationSession:
        if self._session is not None:
            return self._session
        self.connecting = True
        try:
            self.device = await ensure_ready(self.udid)
            session = LocationSession(self.device.udid)
            await session.__aenter__()
            self._session = session
            self.error = None
            return session
        finally:
            self.connecting = False

    async def _disconnect(self) -> None:
        session, self._session = self._session, None
        if session is not None:
            with suppress(Exception):
                await session.__aexit__(None, None, None)

    async def _with_session(self, action: Callable[[LocationSession], Awaitable[T]]) -> T:
        """Executa `action` na sessão; se a conexão caiu, reconecta e tenta mais uma vez."""
        async with self._lock:
            try:
                result = await action(await self._connect())
            except DeviceNotReadyError as e:
                self.error = str(e)
                raise
            except Exception:
                logger.warning("conexão com o iPhone falhou; reconectando", exc_info=True)
                await self._disconnect()
                try:
                    result = await action(await self._connect())
                except Exception as e:
                    self.error = describe_error(e)
                    raise
            self.error = None
            return result

    async def _send(self, lat: float, lon: float) -> None:
        await self._with_session(lambda s: s.set(lat, lon))
        self.current = (lat, lon)

    # ---- comandos ---------------------------------------------------------------------

    async def set_point(self, lat: float, lon: float) -> None:
        validate_coordinates(lat, lon)
        await self._cancel_route()
        await self._send(lat, lon)
        self.mode, self.route, self.progress, self.speed_kmh = "fixed", None, None, None

    async def start_route(self, waypoints: Sequence[LatLon], speed_kmh: float) -> None:
        for lat, lon in waypoints:
            validate_coordinates(lat, lon)
        points = interpolate_route(waypoints, speed_kmh, self.interval_s)
        await self._cancel_route()
        await self._send(*points[0])  # falha logo se o iPhone não estiver disponível
        self.mode, self.route, self.speed_kmh = "route", list(waypoints), speed_kmh
        self.progress = (1, len(points))
        stop = asyncio.Event()
        self._route_stop = stop
        self._route_task = asyncio.create_task(self._play(points, stop))

    async def stop_route(self) -> None:
        """Para a rota e mantém o iPhone no ponto em que ela parou."""
        await self._cancel_route()
        if self.mode == "route":
            self.mode = "fixed"

    async def clear(self) -> None:
        """Volta ao GPS real. Conecta se preciso, para também limpar simulações antigas."""
        await self._cancel_route()
        await self._with_session(lambda s: s.clear())
        self.mode, self.current, self.route, self.progress, self.speed_kmh = "idle", None, None, None, None

    # ---- reprodução de rota -----------------------------------------------------------

    async def _play(self, points: list[LatLon], stop: asyncio.Event) -> None:
        loop = asyncio.get_running_loop()
        started = loop.time()
        try:
            for i, point in enumerate(points[1:], start=1):
                delay = max(0.0, started + i * self.interval_s - loop.time())
                # Espera pelo evento em vez de cancelar a task: assim um envio ao iPhone
                # nunca é interrompido no meio.
                with suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=delay)
                    return
                await self._send(*point)
                self.progress = (i + 1, len(points))
            self.mode = "fixed"  # rota concluída: segura o último ponto
        except Exception as e:
            logger.exception("rota interrompida por erro")
            self.error = f"Rota interrompida: {describe_error(e)}"
            self.mode = "fixed" if self.current else "idle"

    async def _cancel_route(self) -> None:
        task, stop = self._route_task, self._route_stop
        self._route_task = self._route_stop = None
        if task is not None and not task.done():
            assert stop is not None
            stop.set()
            await task

    # ---- estado -----------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        return {
            "device": asdict(self.device) if self.device else None,
            "connected": self._session is not None,
            "connecting": self.connecting,
            "mode": self.mode,
            "current": list(self.current) if self.current else None,
            "route": [list(p) for p in self.route] if self.route else None,
            "route_length_m": route_length_m(self.route) if self.route else None,
            "speed_kmh": self.speed_kmh,
            "progress": {"done": self.progress[0], "total": self.progress[1]} if self.progress else None,
            "interval_s": self.interval_s,
            "error": self.error,
        }
