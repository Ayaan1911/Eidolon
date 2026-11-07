"""IP geolocation: ip-api.com is replaced by httpx.MockTransport. A bad lookup must never
break the trap: the page is still served and the hit is still logged.

Run from backend/:  python -m pytest test_geolocation.py
"""

import asyncio

import httpx
import pytest

from database import Alert
from routers import traps
from services import geolocation

IP_API_OK = {
    "status": "success",
    "city": "Berlin",
    "country": "Germany",
    "lat": 52.5,
    "lon": 13.4,
    "isp": "Example ISP",
    "org": "Example Org",
    "as": "AS64500 Example",
}


@pytest.fixture
def use_real_lookup(monkeypatch):
    """conftest stubs traps.lookup_ip for every test; put the real one back for these."""
    monkeypatch.setattr(traps, "lookup_ip", geolocation.lookup_ip)


def mock_ip_api(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        geolocation.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )


def raises(error: Exception):
    def handler(request):
        raise error

    return handler


def last_alert(session_factory):
    with session_factory() as db:
        return db.query(Alert).order_by(Alert.id.desc()).first()


def test_success_fills_in_the_location(client, use_real_lookup, monkeypatch, session_factory):
    seen = []

    def handler(request):
        seen.append(request.url)
        return httpx.Response(200, json=IP_API_OK)

    mock_ip_api(monkeypatch, handler)
    assert client.get("/trap/t1").status_code == 200

    a = last_alert(session_factory)
    assert (a.location, a.isp, a.latitude) == ("Berlin, Germany", "Example ISP", 52.5)
    # Only the visitor's IP goes to ip-api (in the URL path); nothing else is sent.
    assert [(u.host, u.path) for u in seen] == [("ip-api.com", "/json/testclient")]
    assert seen[0].scheme == "http"  # ip-api's free tier has no HTTPS (tracked for a later pass)


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(200, json={"status": "fail", "message": "reserved range"}),
        lambda request: httpx.Response(429),
        lambda request: httpx.Response(500),
        raises(httpx.ConnectTimeout("timed out")),
        raises(httpx.ReadTimeout("slow")),
        raises(httpx.ConnectError("no route")),
    ],
    ids=["api-fail", "rate-limited", "server-error", "connect-timeout", "read-timeout", "connect-error"],
)
def test_failed_lookup_still_serves_the_page_and_logs_the_hit(
    client, use_real_lookup, monkeypatch, session_factory, handler
):
    mock_ip_api(monkeypatch, handler)
    r = client.get("/trap/t1")

    assert r.status_code == 200
    assert "<html" in r.text.lower()
    a = last_alert(session_factory)
    assert a is not None and a.ip == "testclient"
    assert (a.location, a.isp) == ("Unknown, Unknown", "Unknown")


def test_lookup_ip_returns_an_empty_dict_on_timeout(monkeypatch):
    mock_ip_api(monkeypatch, raises(httpx.ReadTimeout("slow")))
    assert asyncio.run(geolocation.lookup_ip("8.8.8.8")) == {}


def test_login_submission_survives_a_failed_lookup(client, use_real_lookup, monkeypatch, session_factory):
    mock_ip_api(monkeypatch, raises(httpx.ConnectTimeout("timed out")))
    r = client.post("/trap/t1/login", json={"email": "a@b.co", "password_length": 5})
    assert r.status_code == 204
    assert last_alert(session_factory).email == "a@b.co"
