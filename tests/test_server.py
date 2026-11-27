import socket

import pytest

from auriloc.server import PortUnavailableError, loopback_sockets


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_listens_on_ipv4_and_ipv6_loopback():
    port = _free_port()
    sockets = loopback_sockets(port)
    try:
        addresses = {s.getsockname()[0] for s in sockets}
        assert "127.0.0.1" in addresses
        if socket.has_ipv6:
            assert "::1" in addresses
        assert all(s.getsockname()[1] == port for s in sockets)
    finally:
        for s in sockets:
            s.close()


def test_busy_port_gives_a_clear_error():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as taken:
        taken.bind(("127.0.0.1", 0))
        taken.listen()
        port = taken.getsockname()[1]
        with pytest.raises(PortUnavailableError, match=f"Port {port} is not available"):
            loopback_sockets(port)
