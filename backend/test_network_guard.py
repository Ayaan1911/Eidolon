"""The autouse guard in conftest.py must stop tests from reaching the real internet."""

import socket

import pytest


def test_non_loopback_connection_is_refused():
    # 93.184.216.34 is a public address; the guard raises before any packet is sent.
    with pytest.raises(RuntimeError, match="real network connection"):
        socket.create_connection(("93.184.216.34", 80), timeout=1)


def test_loopback_connection_is_not_blocked_by_the_guard():
    # Nothing listens on port 9, so a refusal here is a normal OSError, not the guard's RuntimeError.
    with pytest.raises(OSError):
        socket.create_connection(("127.0.0.1", 9), timeout=1)
