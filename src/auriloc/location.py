"""Location simulation session (iOS 17.4+).

Brings up an RSD tunnel in userspace (no admin rights, no `tunneld`), opens the DVT
instruments channel and exposes set/clear/play_gpx. The simulated location lasts as
long as the session is open: keep the `async with` alive while you need it.
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
        raise ValueError(f"Latitude out of range [-90, 90]: {latitude}")
    if not -180.0 <= longitude <= 180.0:
        raise ValueError(f"Longitude out of range [-180, 180]: {longitude}")


class LocationSession:
    """Usage:

        async with LocationSession() as session:
            await session.set(-23.5505, -46.6333)
            ...  # the location holds while the block is open
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
            raise RuntimeError("Session is not open; use `async with LocationSession()`.")
        return self._simulation

    async def set(self, latitude: float, longitude: float) -> None:
        validate_coordinates(latitude, longitude)
        await self._sim.set(latitude, longitude)

    async def clear(self) -> None:
        await self._sim.clear()

    async def play_gpx(self, path: Path, *, no_wait: bool = False, jitter_ms: int = 0) -> None:
        """Replay a GPX track at the pace of its timestamps (or all at once with no_wait)."""
        await self._sim.play_gpx_file(str(path), disable_sleep=no_wait, timing_randomness_range=jitter_ms)
