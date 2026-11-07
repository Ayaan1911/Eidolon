"""Admin session tokens: signing key separation and verification.

Run from backend/:  python -m pytest test_admin_signing.py
"""

import hashlib
import hmac
import logging
import time

from services import admin_auth, honeytoken
from services.honeytoken import sign


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_issued_token_verifies_and_expires():
    token, expires_at = admin_auth.issue_token(now=1_000_000)
    assert admin_auth.is_valid_admin_token(token, now=1_000_001)
    assert not admin_auth.is_valid_admin_token(token, now=expires_at + 1)


def test_signature_is_not_the_honeytoken_key_signing_the_same_message():
    token, expires_at = admin_auth.issue_token()
    signature = token.rpartition(".")[2]
    # The admin key is derived, so honeytoken signing of the same text gives a different value.
    assert signature != sign(f"admin:{expires_at}")


def test_token_made_the_old_way_is_rejected(monkeypatch):
    # Old scheme: honeytoken key signing "admin:<exp>:<passphrase>" directly.
    expires_at = int(time.time()) + 600
    old_sig = sign(f"admin:{expires_at}:test-admin-key")
    assert not admin_auth.is_valid_admin_token(f"eidolon_admin_{expires_at}.{old_sig}")


def test_token_signed_straight_with_the_passphrase_is_rejected():
    expires_at = int(time.time()) + 600
    sig = hmac.new(b"test-admin-key", f"admin:{expires_at}".encode(), hashlib.sha256).hexdigest()
    assert not admin_auth.is_valid_admin_token(f"eidolon_admin_{expires_at}.{sig}")


def test_rotating_either_secret_revokes_tokens(monkeypatch):
    token, _ = admin_auth.issue_token()
    with monkeypatch.context() as m:
        m.setenv("ADMIN_KEY", "a-brand-new-passphrase")
        assert not admin_auth.is_valid_admin_token(token)
    with monkeypatch.context() as m:
        m.setenv("HONEYTOKEN_SECRET", "a-brand-new-honeytoken-secret")
        assert not admin_auth.is_valid_admin_token(token)
    assert admin_auth.is_valid_admin_token(token)  # unchanged secrets still verify


def test_tampered_expiry_or_signature_is_rejected():
    token, expires_at = admin_auth.issue_token()
    signature = token.rpartition(".")[2]
    assert not admin_auth.is_valid_admin_token(f"eidolon_admin_{expires_at + 99999}.{signature}")
    assert not admin_auth.is_valid_admin_token(token[:-1] + ("0" if token[-1] != "0" else "1"))


def test_a_honeytoken_is_not_an_admin_token(client):
    assert client.get("/api/traps/alerts", headers=bearer(honeytoken.generate_token())).status_code == 401


def test_blank_secrets_never_validate_a_token_even_in_dev_mode(client, monkeypatch):
    # Forge a token the way an attacker would if both secrets were blank.
    monkeypatch.setenv("ADMIN_KEY", "")
    monkeypatch.setenv("HONEYTOKEN_SECRET", "")
    expires_at = int(time.time()) + 600
    key = hmac.new(b"", b"eidolon/admin-session/v1:", hashlib.sha256).digest()
    forged = hmac.new(key, f"admin:{expires_at}".encode(), hashlib.sha256).hexdigest()
    token = f"eidolon_admin_{expires_at}.{forged}"
    assert not admin_auth.is_valid_admin_token(token)
    assert client.get("/api/traps/alerts", headers=bearer(token)).status_code == 401


def test_passphrase_comparison(admin_key):
    assert admin_auth.passphrase_matches(admin_key)
    assert not admin_auth.passphrase_matches(admin_key + "x")
    assert not admin_auth.passphrase_matches(admin_key[:-1])
    assert not admin_auth.passphrase_matches("")
    assert not admin_auth.passphrase_matches("ünïcode-passphrase")  # non-ASCII must not crash


def test_login_is_rate_limited_per_client_ip(client):
    from routers.admin import ADMIN_LOGIN_LIMIT

    allowed = int(ADMIN_LOGIN_LIMIT.split("/")[0])
    codes = [client.post("/api/admin/login", json={"passphrase": "nope"}).status_code for _ in range(allowed + 1)]
    assert codes == [401] * allowed + [429]


def test_passphrase_and_secrets_never_reach_responses_or_logs(client, admin_key, caplog):
    caplog.set_level(logging.DEBUG)
    wrong = client.post("/api/admin/login", json={"passphrase": "my-wrong-guess-123"})
    right = client.post("/api/admin/login", json={"passphrase": admin_key})
    token = right.json()["token"]
    client.get("/api/traps/alerts", headers=bearer(token))
    client.get("/api/traps/alerts", headers=bearer("junk"))

    everything = wrong.text + caplog.text
    assert "my-wrong-guess-123" not in everything
    assert admin_key not in everything + token  # the token does not contain the passphrase
    assert "test-honeytoken-secret" not in everything + token
