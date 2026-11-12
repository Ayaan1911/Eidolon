"""Shared test isolation. Every test gets, automatically:

- a fresh in-memory SQLite database (nothing touches eidolon.db),
- monkeypatched environment variables (restored after the test, never mutated at import),
- cleared in-memory rate-limit and breach-metadata state,
- stubbed geolocation and ntfy (no network),
- a guard that fails any test making a real outbound network connection, and
- database.SessionLocal pointed at that database (restored afterwards).

Test modules must not set os.environ or module attributes at
import time; use these fixtures and the `monkeypatch` fixture instead.

Run from backend/:  python -m pytest
"""

import ipaddress
import os
import socket
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# main.py checks the secrets when it is imported, before any fixture runs, so dev mode is
# switched on here. The tests that exercise the check itself turn it off with monkeypatch.
os.environ.setdefault("EIDOLON_ENV", "dev")

import main  # noqa: E402
import database
from database import Trap
from routers import exposure, ready, traps
from services import admin_auth, breach_check

ADMIN_KEY = "test-admin-key"
HONEYTOKEN_SECRET = "test-honeytoken-secret"

FAKE_GEO = {
    "city": "Ashburn",
    "country": "United States",
    "lat": 1.0,
    "lon": 2.0,
    "isp": "Example Broadband",
    "org": "Example Networks Ltd",
    "as": "AS64500 Example Networks",
}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("ADMIN_KEY", ADMIN_KEY)
    monkeypatch.setenv("HONEYTOKEN_SECRET", HONEYTOKEN_SECRET)
    # Anything a developer's real backend/.env might have loaded must not leak into tests.
    for name in ("GITHUB_TOKEN", "NTFY_TOPIC", "RENDER", "RENDER_GIT_COMMIT", "DATABASE_URL", "RETENTION_DAYS", "TRUSTED_PROXY_HOPS", "PUBLIC_BASE_URL"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture(autouse=True)
def _block_outbound_network(monkeypatch):
    """Fail loudly if a test tries a real network connection.

    Loopback is still allowed: on Windows the asyncio event loop talks to itself over a
    127.0.0.1 socket pair, and TestClient needs the event loop. Anything else (a real
    API host, an IP on the internet) raises, so a forgotten mock cannot hide as a pass.
    """
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def is_loopback(address):
        # AF_UNIX addresses are plain strings; AF_INET/AF_INET6 are (host, port, ...) tuples.
        if not isinstance(address, tuple):
            return True
        host = address[0]
        if host == "localhost":
            return True
        try:
            return ipaddress.ip_address(host).is_loopback
        except ValueError:
            return False  # a hostname that is not localhost

    def guard(real):
        def wrapper(self, address):
            if not is_loopback(address):
                raise RuntimeError(f"Test tried a real network connection to {address!r}; mock it")
            return real(self, address)

        return wrapper

    monkeypatch.setattr(socket.socket, "connect", guard(real_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guard(real_connect_ex))


@pytest.fixture(autouse=True)
def _reset_in_memory_state():
    exposure.limiter.reset()
    breach_check._metadata_cache.clear()
    traps._last_alert_at.clear()
    ready._cache = None
    yield
    exposure.limiter.reset()
    breach_check._metadata_cache.clear()
    traps._last_alert_at.clear()
    ready._cache = None


@pytest.fixture(autouse=True)
def _no_network_in_traps(monkeypatch):
    async def fake_lookup(ip):
        return dict(FAKE_GEO)

    async def no_alert(*args, **kwargs):
        return None

    monkeypatch.setattr(traps, "lookup_ip", fake_lookup)
    monkeypatch.setattr(traps, "send_ntfy_alert", no_alert)


BACKEND_DIR = Path(__file__).resolve().parent


def alembic_config(connection=None) -> Config:
    """Alembic settings; with a connection, migrations run on it instead of building their own."""
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


@pytest.fixture
def engine():
    """A fresh in-memory SQLite database built by the real migrations (not create_all)."""
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with eng.begin() as connection:
        command.upgrade(alembic_config(connection), "head")
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _override_db(monkeypatch, session_factory):
    """Point the app at this test's fresh database (routes open sessions through database.SessionLocal)."""
    monkeypatch.setattr(database, "SessionLocal", session_factory)


@pytest.fixture
def make_trap(session_factory):
    """Create a real trap row. Unknown trap ids are ignored by the trap routes, so any test
    that wants a hit logged needs a trap that exists."""

    def make(trap_id: str = "t1", name: str = "Test trap") -> str:
        with session_factory() as db:
            db.add(Trap(id=trap_id, name=name))
            db.commit()
        return trap_id

    return make


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def admin_key():
    return ADMIN_KEY


@pytest.fixture
def admin_headers():
    token, _ = admin_auth.issue_token()
    return {"Authorization": f"Bearer {token}"}
