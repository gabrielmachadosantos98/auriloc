"""Protect the local API from websites open in the user's browser.

The API has no authentication: anything that can reach it can move the iPhone. Binding to
loopback keeps other machines out, but a website can still reach it through the browser:

* DNS rebinding: an attacker's domain re-resolves to 127.0.0.1, so its page becomes
  "same-origin" with the API and can read the status (UDID, device name, location) and
  send commands. Blocked by accepting only requests whose Host header is a loopback name.
* Cross-site requests: browsers already block JSON POSTs from other origins (CORS
  preflight), but as defense in depth any state-changing request that carries a foreign
  Origin header is rejected too. Requests without Origin (curl, scripts, test runners)
  are allowed.
"""

from collections.abc import Awaitable, Callable, Iterable
from typing import Any, Optional
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

LOOPBACK_NAMES = frozenset({"localhost", "127.0.0.1", "::1"})
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

Scope = dict[str, Any]
ASGIApp = Callable[[Scope, Callable[[], Awaitable[Any]], Callable[[Any], Awaitable[None]]], Awaitable[None]]


def host_name(host_header: str) -> str:
    """Host header without the port: 'localhost:8765' -> 'localhost', '[::1]:8765' -> '::1'."""
    value = host_header.strip().lower()
    if value.startswith("["):
        end = value.find("]")
        return value[1:end] if end != -1 else value
    if value.count(":") == 1:
        return value.split(":", 1)[0]
    return value


def origin_name(origin: str) -> Optional[str]:
    """Host name of an Origin header, or None for 'null' and malformed values."""
    try:
        return urlsplit(origin.strip()).hostname
    except ValueError:
        return None


class LocalOnlyMiddleware:
    """Reject requests not addressed to a loopback host, and writes from foreign origins."""

    def __init__(self, app: ASGIApp, allowed_hosts: Iterable[str] = LOOPBACK_NAMES) -> None:
        self.app = app
        self.allowed_hosts = frozenset(h.lower() for h in allowed_hosts)

    async def __call__(self, scope: Scope, receive: Any, send: Any) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}

        if host_name(headers.get("host", "")) not in self.allowed_hosts:
            await self._deny(scope, receive, send, "Requests must be addressed to localhost.")
            return

        origin = headers.get("origin")
        if origin is not None and scope.get("method", "GET") not in SAFE_METHODS:
            if origin_name(origin) not in self.allowed_hosts:
                await self._deny(scope, receive, send, "Requests from other websites are not allowed.")
                return

        await self.app(scope, receive, send)

    @staticmethod
    async def _deny(scope: Scope, receive: Any, send: Any, message: str) -> None:
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await JSONResponse({"detail": message}, status_code=403)(scope, receive, send)
