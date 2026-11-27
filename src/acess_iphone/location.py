"""Sessão de simulação de localização (iOS 17.4+).

Sobe um túnel RSD em userspace (sem admin, sem `tunneld`), abre o canal DVT de
instrumentação e expõe set/clear/play_gpx. A localização simulada depende da
sessão aberta: mantenha o `async with` vivo enquanto quiser a posição falsa.
"""

from contextlib import AsyncExitStack
from pathlib import Path
from types import TracebackType
from typing import Optional, Self

from pymobiledevice3.remote.userspace_tunnel import UserspaceRsdTunnel
from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
from pymobiledevice3.services.dvt.instruments.location_simulation import LocationSimulation


def validate_coordinates(latitude: float, longitude: float) -> None:
    if not -90.0 <= latitude <= 90.0:
        raise ValueError(f"Latitude fora do intervalo [-90, 90]: {latitude}")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError(f"Longitude fora do intervalo [-180, 180]: {longitude}")


class LocationSession:
    """Uso:

        async with LocationSession() as session:
            await session.set(-23.5505, -46.6333)
            ...  # a localização vale enquanto o bloco estiver aberto
    """

    def __init__(self, udid: Optional[str] = None) -> None:
        self.udid = udid
        self._stack: Optional[AsyncExitStack] = None
        self._simulation: Optional[LocationSimulation] = None

    async def __aenter__(self) -> Self:
        stack = AsyncExitStack()
        try:
            rsd = await stack.enter_async_context(UserspaceRsdTunnel(serial=self.udid))
            dvt = await stack.enter_async_context(DvtProvider(rsd))
            self._simulation = await stack.enter_async_context(LocationSimulation(dvt))
        except BaseException:
            await stack.aclose()
            raise
        self._stack = stack
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        stack, self._stack, self._simulation = self._stack, None, None
        if stack is not None:
            await stack.aclose()

    @property
    def _sim(self) -> LocationSimulation:
        if self._simulation is None:
            raise RuntimeError("Sessão não está aberta; use `async with LocationSession()`.")
        return self._simulation

    async def set(self, latitude: float, longitude: float) -> None:
        validate_coordinates(latitude, longitude)
        await self._sim.set(latitude, longitude)

    async def clear(self) -> None:
        await self._sim.clear()

    async def play_gpx(self, path: Path, *, no_wait: bool = False, jitter_ms: int = 0) -> None:
        """Reproduz a rota de um GPX no ritmo dos timestamps (ou de uma vez com no_wait)."""
        await self._sim.play_gpx_file(str(path), disable_sleep=no_wait, timing_randomness_range=jitter_ms)
