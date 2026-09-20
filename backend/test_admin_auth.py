"""Admin auth checks: login, token verification, and which endpoints are locked.

Run from backend/:  python test_admin_auth.py  (also collected by pytest)
Uses an in-memory DB, so it never touches eidolon.db.
"""

import os

os.environ["ADMIN_KEY"] = "correct horse battery staple"
os.environ["HONEYTOKEN_SECRET"] = "test-honeytoken-secret"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import main
from database import Base, get_db
from services import admin_auth
from services.honeytoken import generate_token

_engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(_engine)
_Session = sessionmaker(bind=_engine)


def _get_test_db():
    db = _Session()
    try:
        yield db
    finally:
        db.close()


main.app.dependency_overrides[get_db] = _get_test_db
client = TestClient(main.app)
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


def test_rotating_admin_key_revokes_tokens():
    token, _ = admin_auth.issue_token()
    os.environ["ADMIN_KEY"] = "a different passphrase"
    try:
        assert not admin_auth.is_valid_admin_token(token)
    finally:
        os.environ["ADMIN_KEY"] = "correct horse battery staple"
    assert admin_auth.is_valid_admin_token(token)


def test_locked_endpoints_reject_without_valid_token():
    expired, _ = admin_auth.issue_token(now=0)
    for headers in (None, bearer("nonsense"), bearer(expired), {"Authorization": "Basic abc"}):
        r = client.post("/api/traps", json=NEW_TRAP, headers=headers)
        assert r.status_code == 401 and r.json() == {"detail": "Unauthorized"}, (headers, r.text)
        assert client.get("/api/traps/alerts", headers=headers).status_code == 401


def test_locked_endpoints_accept_valid_token():
    token, _ = admin_auth.issue_token()
    r = client.post("/api/traps", json=NEW_TRAP, headers=bearer(token))
    assert r.status_code == 200 and "trap_url" in r.json()
    assert client.get("/api/traps/alerts", headers=bearer(token)).status_code == 200


def test_public_endpoints_stay_public():
    # Mirror tools and the decoy-key flow must not need a token.
    assert client.post("/api/exposure/password", json={"password": "hunter2"}).status_code == 200
    assert client.post("/api/findings/abc/deploy-decoy").status_code == 200
    assert client.get("/health").status_code == 200


def test_login():
    # Kept last-ish: login is rate limited to 5/minute per IP.
    wrong = client.post("/api/admin/login", json={"passphrase": "nope"})
    assert wrong.status_code == 401 and wrong.json() == {"detail": "Unauthorized"}
    ok = client.post("/api/admin/login", json={"passphrase": os.environ["ADMIN_KEY"]})
    assert ok.status_code == 200
    body = ok.json()
    assert admin_auth.is_valid_admin_token(body["token"]) and body["expires_at"] > 0
    assert client.get("/api/traps/alerts", headers=bearer(body["token"])).status_code == 200

    # ADMIN_KEY unset: even an empty passphrase must not log in.
    saved = os.environ.pop("ADMIN_KEY")
    try:
        assert client.post("/api/admin/login", json={"passphrase": ""}).status_code == 401
    finally:
        os.environ["ADMIN_KEY"] = saved

    # Brute-force guard: 4 attempts so far in this window, so the 6th is throttled.
    codes = [client.post("/api/admin/login", json={"passphrase": "x"}).status_code for _ in range(3)]
    assert codes[-1] == 429, codes


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
