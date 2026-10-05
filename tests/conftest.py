"""Global pytest fixtures for the test suite."""

from __future__ import annotations

import socket
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def isolate_environment_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test runs with empty API keys by default.

    No test can read a live API key from .env or the host environment.
    A test that needs a key sets a placeholder itself.
    """
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("GEMINI_API_KEY", "")


# ===========================================================================
# The one `_no_socket` fixture
#
# Rule 3's neighbour: a unit test that silently reached the network would read
# live market data and its figures would move between runs. `_no_socket`
# refuses every outbound connection, so such a test fails instead of waiting.
#
# Until P1b-windows-gate this fixture existed in four copies
# (test_cli_overrides.py:36, test_p14d_finance_leases.py:71,
# test_pipeline.py:75, test_routes.py:1056) that differed only in the words of
# their message. One rule copied four times goes stale in three of them, so
# there is now one definition and the four copies are deleted.
#
# **Loopback is allowed, every other address is refused.** The reason is
# measured, not stylistic: on Windows `asyncio.ProactorEventLoop` builds its
# own self-pipe with `socket.socketpair()`, which connects a socket to
# `127.0.0.1`. A blanket refusal broke that self-pipe, so every Starlette
# `TestClient` request made after the patch returned 500 and thirteen tests
# failed on this machine for a reason that had nothing to do with the product.
# A connection to `127.0.0.1`, `::1` or `localhost` never leaves the machine,
# so allowing it costs nothing the fixture was there to buy.
#
# Two tests in `tests/unit/test_routes.py` hold this contract in place:
# `test_no_socket_refuses_an_address_that_leaves_the_machine` and
# `test_no_socket_allows_the_loopback_address`. Without the first, a later
# change that turns the fixture into a no-op would pass every test in the
# suite.
# ===========================================================================

_REAL_CONNECT = socket.socket.connect
_REAL_CONNECT_EX = socket.socket.connect_ex
_REAL_CREATE_CONNECTION = socket.create_connection

#: The addresses that do not leave this machine.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def _host_of(address: Any) -> str:
    """The host part of a socket address, as text.

    `connect` takes `(host, port)` for AF_INET, `(host, port, flowinfo,
    scope_id)` for AF_INET6, and a path for AF_UNIX. Anything that is not a
    recognised address shape is returned as its `repr`, which belongs to no
    allowed host and is therefore refused.
    """
    if isinstance(address, (tuple, list)) and address:
        host = address[0]
    else:
        host = address
    if isinstance(host, (bytes, bytearray)):
        return bytes(host).decode("utf-8", "replace")
    if isinstance(host, str):
        return host
    return repr(host)


def _is_loopback(address: Any) -> bool:
    return _host_of(address) in LOOPBACK_HOSTS


@pytest.fixture
def _no_socket(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse every outbound connection for the length of one test.

    A connection to the loopback address is allowed and reaches the real
    socket; every other address raises `AssertionError`.
    """

    def _connect(self: socket.socket, address: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_loopback(address):
            return _REAL_CONNECT(self, address, *args, **kwargs)
        raise AssertionError(f"a unit test opened a network connection: {address!r}")

    def _connect_ex(self: socket.socket, address: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_loopback(address):
            return _REAL_CONNECT_EX(self, address, *args, **kwargs)
        raise AssertionError(f"a unit test opened a network connection: {address!r}")

    def _create_connection(address: Any, *args: Any, **kwargs: Any) -> Any:
        if _is_loopback(address):
            return _REAL_CREATE_CONNECTION(address, *args, **kwargs)
        raise AssertionError(f"a unit test opened a network connection: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", _connect)
    monkeypatch.setattr(socket.socket, "connect_ex", _connect_ex)
    monkeypatch.setattr(socket, "create_connection", _create_connection)
