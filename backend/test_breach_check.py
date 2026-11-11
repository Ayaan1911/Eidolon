"""Email breach lookup, with the XposedOrNot API replaced by httpx.MockTransport.

Run from backend/:  python -m pytest test_breach_check.py
"""

import httpx
import pytest

from services import breach_check

METADATA = {
    "exposedBreaches": [
        {
            "breachID": "LeakyForum",
            "breachedDate": "2019-03-01T00:00:00",
            "exposedData": ["Emails", "Passwords"],
            "passwordRisk": "plaintext",
        },
        {
            "breachID": "QuietShop",
            "breachedDate": "2021-07-15T00:00:00",
            "exposedData": ["Emails"],
            "passwordRisk": "hardtocrack",
        },
    ]
}


def mock_xposed(monkeypatch, handler):
    """Make breach_check's httpx.AsyncClient talk to `handler` instead of the internet."""
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        breach_check.httpx, "AsyncClient", lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)
    )


def api(breaches=None, status=200):
    """A handler that answers the two endpoints breach_check calls."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/breaches"):
            return httpx.Response(200, json=METADATA)
        if status != 200:
            return httpx.Response(status)
        # The real API wraps the name list in an extra list.
        return httpx.Response(200, json={"breaches": [breaches]})

    return handler


def failing(error: Exception):
    def handler(request):
        raise error

    return handler


def test_breached_email_is_reported_with_details(client, monkeypatch):
    mock_xposed(monkeypatch, api(["LeakyForum", "QuietShop"]))
    body = client.post("/api/exposure/email", json={"email": "someone@example.com"}).json()

    assert body["total_breaches"] == 2
    leaky, quiet = body["breaches"]
    assert (leaky["name"], leaky["date"], leaky["severity"]) == ("LeakyForum", "2019-03-01", "High")
    assert leaky["data_exposed"] == ["Emails", "Passwords"]
    assert (quiet["name"], quiet["severity"]) == ("QuietShop", "Medium")
    assert "risk_score" not in body and "score" not in body  # narrative findings only, never a number


def test_clean_email_is_reported_as_clean(client, monkeypatch):
    mock_xposed(monkeypatch, api(status=404))  # the API answers 404 for "not found in any breach"
    body = client.post("/api/exposure/email", json={"email": "fresh@example.com"}).json()
    assert (body["total_breaches"], body["breaches"]) == (0, [])


def test_breach_missing_from_metadata_is_still_listed_with_defaults(client, monkeypatch):
    mock_xposed(monkeypatch, api(["BrandNewBreach"]))
    body = client.post("/api/exposure/email", json={"email": "someone@example.com"}).json()
    b = body["breaches"][0]
    assert (b["name"], b["date"], b["data_exposed"]) == ("BrandNewBreach", "Unknown", ["Email addresses"])


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectTimeout("timed out"), httpx.ReadTimeout("slow"), httpx.ConnectError("no route")],
    ids=["connect-timeout", "read-timeout", "connect-error"],
)
def test_upstream_network_failure_returns_a_safe_502(client, monkeypatch, error):
    mock_xposed(monkeypatch, failing(error))
    r = client.post("/api/exposure/email", json={"email": "someone@example.com"})
    assert r.status_code == 502
    assert r.json()["detail"].startswith("XposedOrNot API request failed")


def test_upstream_server_error_returns_a_safe_502(client, monkeypatch):
    mock_xposed(monkeypatch, api(status=500))
    r = client.post("/api/exposure/email", json={"email": "someone@example.com"})
    assert r.status_code == 502


def test_invalid_email_is_rejected_before_any_lookup(client, monkeypatch):
    mock_xposed(monkeypatch, failing(AssertionError("no upstream call for an invalid email")))
    assert client.post("/api/exposure/email", json={"email": "not-an-email"}).status_code == 422


def test_password_never_goes_to_this_server(client):
    # The breached-password check runs in the browser (k-anonymity), so no route may accept a password.
    assert client.post("/api/exposure/password", json={"password": "x"}).status_code in (404, 405)
