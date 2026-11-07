"""Shared test isolation. Every test gets, automatically:

- a fresh in-memory SQLite database (nothing touches eidolon.db),
- monkeypatched environment variables (restored after the test, never mutated at import),
- cleared in-memory rate-limit and breach-metadata state,
- stubbed geolocation and ntfy (no network),
- a guard that fails any test making a real outbound network connection, and
- an app.dependency_overrides that is restored afterwards.

Test modules must not set os.environ, app.dependency_overrides or module attributes at
import time; use these fixtures and the `monkeypatch` fixture instead.

Run from backend/:  python -m pytest
"""

import ipaddress
import os
import socket

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# main.py checks the secrets when it is imported, before any fixture runs, so dev mode is
# switched on here. The tests that exercise the check itself turn it off with monkeypatch.
os.environ.setdefault("EIDOLON_ENV", "dev")

import main  # noqa: E402
from database import Base, get_db
from routers import exposure, traps
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
    for name in ("GITHUB_TOKEN", "NTFY_TOPIC", "RENDER_GIT_COMMIT"):
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
    yield
    exposure.limiter.reset()
    breach_check._metadata_cache.clear()


@pytest.fixture(autouse=True)
def _no_network_in_traps(monkeypatch):
    async def fake_lookup(ip):
        return dict(FAKE_GEO)

    async def no_alert(*args, **kwargs):
        return None

    monkeypatch.setattr(traps, "lookup_ip", fake_lookup)
    monkeypatch.setattr(traps, "send_ntfy_alert", no_alert)


@pytest.fixture
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def session_factory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture(autouse=True)
def _override_db(session_factory):
    """Point the app at this test's fresh database, then restore the overrides."""
    saved = dict(main.app.dependency_overrides)

    def get_test_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    main.app.dependency_overrides[get_db] = get_test_db
    yield
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides.update(saved)


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
