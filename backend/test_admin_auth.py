"""Admin auth checks: login, token verification, and which endpoints are locked.

Run from backend/:  python -m pytest test_admin_auth.py
Fixtures (fresh in-memory DB, env, rate-limit reset) come from conftest.py.
"""

from services import admin_auth
from services.honeytoken import generate_token

NEW_TRAP = {"name": "Prod DB — backup"}


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_token_rules():
    token, expires_at = admin_auth.issue_token()
    assert admin_auth.is_valid_admin_token(token)
    assert not admin_auth.is_valid_admin_token(None)
    assert not admin_auth.is_valid_admin_token("")
    assert not admin_auth.is_valid_admin_token(token[:-1] + ("0" if token[-1] != "0" else "1"))
    # Expiry is baked into the signed payload: past it, the same token is dead...
    assert not admin_auth.is_valid_admin_token(token, now=expires_at + 1)
    # ...and rewriting the expiry to extend it breaks the signature.
    _, _, sig = token.rpartition(".")
    assert not admin_auth.is_valid_admin_token(f"{admin_auth.TOKEN_PREFIX}{expires_at + 9999}.{sig}")
    # A honeytoken (same HMAC key) is not an admin token.
    assert not admin_auth.is_valid_admin_token(generate_token())
    # Non-ASCII garbage must be a clean "no", not a crash.
    assert not admin_auth.is_valid_admin_token(f"{admin_auth.TOKEN_PREFIX}{expires_at}.—é")


def test_rotating_admin_key_revokes_tokens(monkeypatch):
    token, _ = admin_auth.issue_token()
    with monkeypatch.context() as m:
        m.setenv("ADMIN_KEY", "a different passphrase")
        assert not admin_auth.is_valid_admin_token(token)
    assert admin_auth.is_valid_admin_token(token)


def test_locked_endpoints_reject_without_valid_token(client):
    expired, _ = admin_auth.issue_token(now=0)
    for headers in (None, bearer("nonsense"), bearer(expired), {"Authorization": "Basic abc"}):
        r = client.post("/api/traps", json=NEW_TRAP, headers=headers)
        assert r.status_code == 401 and r.json() == {"detail": "Unauthorized"}, (headers, r.text)
        assert client.get("/api/traps/alerts", headers=headers).status_code == 401


def test_locked_endpoints_accept_valid_token(client):
    token, _ = admin_auth.issue_token()
    r = client.post("/api/traps", json=NEW_TRAP, headers=bearer(token))
    assert r.status_code == 200 and "trap_url" in r.json()
    assert client.get("/api/traps/alerts", headers=bearer(token)).status_code == 200


def test_public_endpoints_stay_public(client):
    # Mirror tools must not need a token. (deploy-decoy used to be listed here; Pass 4
    # made it admin-only, see test_mint_routes.py.)
    assert client.post("/api/exposure/email", json={"email": "bad"}).status_code == 422  # reachable, no token asked
    assert client.get("/health").status_code == 200


def test_login(client, monkeypatch, admin_key):
    # Login is rate limited to 5/minute per IP (the limiter is reset before each test).
    wrong = client.post("/api/admin/login", json={"passphrase": "nope"})
    assert wrong.status_code == 401 and wrong.json() == {"detail": "Unauthorized"}
    ok = client.post("/api/admin/login", json={"passphrase": admin_key})
    assert ok.status_code == 200
    body = ok.json()
    assert admin_auth.is_valid_admin_token(body["token"]) and body["expires_at"] > 0
    assert client.get("/api/traps/alerts", headers=bearer(body["token"])).status_code == 200

    # ADMIN_KEY unset: even an empty passphrase must not log in.
    with monkeypatch.context() as m:
        m.delenv("ADMIN_KEY")
        assert client.post("/api/admin/login", json={"passphrase": ""}).status_code == 401

    # Brute-force guard: 3 attempts so far in this window, so the 6th is throttled.
    codes = [client.post("/api/admin/login", json={"passphrase": "x"}).status_code for _ in range(3)]
    assert codes[-1] == 429, codes

