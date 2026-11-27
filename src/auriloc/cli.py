"""`auriloc` command line.

Examples (negative coordinates work as-is):
    auriloc devices
    auriloc set -23.5505 -46.6333
    auriloc route path.gpx
    auriloc clear
    auriloc web
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Coroutine
from pathlib import Path
from typing import Any, Optional

from pymobiledevice3.lockdown import create_using_usbmux
from pymobiledevice3.services.amfi import AmfiService

from auriloc.device import DeviceNotReadyError, ensure_ready, get_device_info, list_usb_udids
from auriloc.location import LocationSession, validate_coordinates


async def _wait_forever() -> None:
    await asyncio.Event().wait()


async def cmd_devices(_: argparse.Namespace) -> None:
    udids = await list_usb_udids()
    if not udids:
        print("No iPhone connected over USB. Check the cable and that Apple Devices (or iTunes) is installed.")
        return
    for udid in udids:
        info = await get_device_info(udid)
        dev = "on" if info.developer_mode else "OFF"
        print(f"{info.name}  |  iOS {info.ios_version}  |  Developer Mode: {dev}  |  {info.udid}")


async def cmd_reveal(args: argparse.Namespace) -> None:
    lockdown = await create_using_usbmux(serial=args.udid)
    try:
        await AmfiService(lockdown).reveal_developer_mode_option_in_ui()
    finally:
        await lockdown.close()
    print("Done: the option should now appear under Settings > Privacy & Security > Developer Mode.")


async def cmd_set(args: argparse.Namespace) -> None:
    validate_coordinates(args.latitude, args.longitude)
    info = await ensure_ready(args.udid)
    async with LocationSession(info.udid) as session:
        await session.set(args.latitude, args.longitude)
        print(f"Location of '{info.name}' set to {args.latitude}, {args.longitude}.")
        print("Keep this terminal open. Press Ctrl+C to stop and return to real GPS.")
        try:
            await _wait_forever()
        finally:
            await session.clear()


async def cmd_clear(args: argparse.Namespace) -> None:
    info = await ensure_ready(args.udid)
    async with LocationSession(info.udid) as session:
        await session.clear()
    print("Simulation cleared; the iPhone is back on real GPS.")


async def cmd_route(args: argparse.Namespace) -> None:
    if not args.gpx.is_file():
        raise FileNotFoundError(f"GPX file not found: {args.gpx}")
    info = await ensure_ready(args.udid)
    async with LocationSession(info.udid) as session:
        print(f"Playing {args.gpx.name} on '{info.name}'... (Ctrl+C to stop)")
        try:
            await session.play_gpx(args.gpx, no_wait=args.no_wait, jitter_ms=args.jitter_ms)
            print("Route finished; holding the last point. Press Ctrl+C to stop.")
            await _wait_forever()
        finally:
            await session.clear()


async def cmd_web(args: argparse.Namespace) -> None:
    from auriloc.server import serve  # import FastAPI/uvicorn only when needed

    await serve(host=args.host, port=args.port, udid=args.udid, open_browser=not args.no_browser)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="auriloc", description="Simulate the location of a real iPhone over USB.")
    parser.add_argument("--udid", help="device UDID (default: the first one connected over USB)")
    parser.add_argument("-v", "--verbose", action="store_true", help="show detailed logs")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("devices", help="list connected iPhones and prerequisites").set_defaults(func=cmd_devices)
    sub.add_parser("reveal", help="make the Developer Mode option appear in Settings").set_defaults(func=cmd_reveal)

    p_set = sub.add_parser("set", help="set a fixed location (holds until Ctrl+C)")
    p_set.add_argument("latitude", type=float)
    p_set.add_argument("longitude", type=float)
    p_set.set_defaults(func=cmd_set)

    sub.add_parser("clear", help="remove the simulated location").set_defaults(func=cmd_clear)

    p_route = sub.add_parser("route", help="play a route from a GPX file")
    p_route.add_argument("gpx", type=Path)
    p_route.add_argument("--no-wait", action="store_true", help="ignore GPX timestamps and jump point to point")
    p_route.add_argument("--jitter-ms", type=int, default=0, help="random timing variation between points (ms)")
    p_route.set_defaults(func=cmd_route)

    p_web = sub.add_parser("web", help="open the map in the browser to click points and draw routes")
    p_web.add_argument("--port", type=int, default=8765)
    p_web.add_argument("--host", default="127.0.0.1", help="server address (default: this computer only)")
    p_web.add_argument("--no-browser", action="store_true", help="do not open the browser automatically")
    p_web.set_defaults(func=cmd_web)
    return parser


def _run(coro: Coroutine[Any, Any, None]) -> None:
    # pymobiledevice3 uses SelectorEventLoop on Windows (Proactor has issues with its sockets).
    loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
    asyncio.run(coro, loop_factory=loop_factory)


def main(argv: Optional[list[str]] = None) -> int:
    # Messages like "Location set" must show up immediately, even when output is redirected.
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[union-attr]
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    try:
        _run(args.func(args))
    except KeyboardInterrupt:
        print("\nStopped.")
    except (DeviceNotReadyError, ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
