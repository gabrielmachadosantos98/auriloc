import asyncio
import json
from typing import Any, Optional

import pytest

from auriloc.security import LocalOnlyMiddleware, host_name, origin_name


async def _ok_app(scope: dict[str, Any], receive: Any, send: Any) -> None:
    await send({"type": "http.response.start", "status": 200, "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body", "body": b"ok"})


def call(method: str, host: str, origin: Optional[str] = None) -> tuple[int, Any]:
    """Run one request through the middleware and return (status, body)."""
    headers = [(b"host", host.encode())]
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    scope = {"type": "http", "method": method, "path": "/api/status", "headers": headers}
    sent: list[dict[str, Any]] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    asyncio.run(LocalOnlyMiddleware(_ok_app)(scope, receive, send))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, (json.loads(body) if status == 403 else body)


@pytest.mark.parametrize("host", ["localhost:8765", "127.0.0.1:8765", "[::1]:8765", "LOCALHOST:8765", "localhost"])
def test_loopback_hosts_are_allowed(host):
    assert call("GET", host)[0] == 200


@pytest.mark.parametrize("host", ["evil.example:8765", "evil.example", "192.168.0.10:8765", "", "localhost.evil.example"])
def test_dns_rebinding_hosts_are_rejected(host):
    status, body = call("GET", host)
    assert status == 403
    assert "localhost" in body["detail"]


def test_rebinding_cannot_send_commands():
    assert call("POST", "evil.example:8765", origin="http://evil.example:8765")[0] == 403


@pytest.mark.parametrize("origin", ["https://evil.example", "null", "http://192.168.0.10:8765"])
def test_writes_from_foreign_origins_are_rejected(origin):
    status, body = call("POST", "localhost:8765", origin=origin)
    assert status == 403
    assert "other websites" in body["detail"]


@pytest.mark.parametrize("origin", ["http://localhost:8765", "http://127.0.0.1:8765", "http://[::1]:8765"])
def test_writes_from_the_map_page_are_allowed(origin):
    assert call("POST", "localhost:8765", origin=origin)[0] == 200


def test_scripts_without_origin_are_allowed():
    # curl, PowerShell and test runners send no Origin header.
    assert call("POST", "127.0.0.1:8765")[0] == 200


def test_reads_ignore_origin():
    # Browsers already block cross-origin reads (no CORS headers); only Host matters for GET.
    assert call("GET", "localhost:8765", origin="https://evil.example")[0] == 200


@pytest.mark.parametrize(
    ("header", "expected"),
    [("localhost:8765", "localhost"), ("[::1]:8765", "::1"), ("127.0.0.1", "127.0.0.1"), ("Example.COM:80", "example.com")],
)
def test_host_name(header, expected):
    assert host_name(header) == expected


@pytest.mark.parametrize(
    ("origin", "expected"),
    [("http://localhost:8765", "localhost"), ("http://[::1]:8765", "::1"), ("null", None), ("http://[bad", None)],
)
def test_origin_name(origin, expected):
    assert origin_name(origin) == expected
