"""Honeytoken signing/verification, and what /api/internal/verify shows the caller.

Run from backend/:  python -m pytest test_honeytoken.py
"""

import pytest

from routers import traps
from services import honeytoken

# Every bad token must look identical to the caller: same status, same body.
GENERIC_401 = {"detail": "Invalid or expired API key"}


def flip_last_char(text: str) -> str:
    return text[:-1] + ("0" if text[-1] != "0" else "1")


def test_a_generated_token_verifies():
    assert honeytoken.is_valid_token(honeytoken.generate_token())


def test_a_token_tied_to_a_finding_verifies():
    token = honeytoken.generate_token("abc123finding")
    assert "abc123finding" in token  # the finding id travels inside the payload
    assert honeytoken.is_valid_token(token)


def test_tampered_payload_is_rejected():
    token = honeytoken.generate_token()
    prefix = honeytoken.TOKEN_PREFIX
    payload, _, sig = token[len(prefix):].rpartition(".")
    # Change one character of the payload but keep the original signature.
    assert not honeytoken.is_valid_token(f"{prefix}{flip_last_char(payload)}.{sig}")


def test_tampered_signature_is_rejected():
    assert not honeytoken.is_valid_token(flip_last_char(honeytoken.generate_token()))


def test_token_signed_with_another_secret_is_rejected(monkeypatch):
    token = honeytoken.generate_token()
    monkeypatch.setenv("HONEYTOKEN_SECRET", "a-different-secret")
    assert not honeytoken.is_valid_token(token)


def test_token_is_rejected_when_the_secret_is_not_configured(monkeypatch):
    token = honeytoken.generate_token()
    monkeypatch.delenv("HONEYTOKEN_SECRET")
    assert not honeytoken.is_valid_token(token)


@pytest.mark.parametrize(
    "bad",
    [
        "",
        None,
        "not-a-token",
        "eidolon_live_",  # prefix only
        "eidolon_live_abc",  # no signature separator
        "eidolon_live_abc.",  # empty signature
        "eidolon_live_.deadbeef",  # empty payload
        "wrong_prefix_abc.deadbeef",
    ],
)
def test_malformed_tokens_are_rejected(bad):
    assert not honeytoken.is_valid_token(bad)


@pytest.fixture
def alerts(monkeypatch):
    """Collects the ntfy alerts the verify endpoint would send."""
    sent = []

    async def record(title, fields):
        sent.append((title, fields))

    monkeypatch.setattr(traps, "send_ntfy_alert", record)
    return sent


def test_verify_endpoint_answers_every_bad_key_the_same_way(client, alerts):
    tampered = flip_last_char(honeytoken.generate_token())
    for headers in ({}, {"X-API-Key": "junk"}, {"X-API-Key": tampered}, {"Authorization": "Bearer junk"}):
        r = client.get("/api/internal/verify", headers=headers)
        assert (r.status_code, r.json()) == (401, GENERIC_401)
    assert alerts == []  # nothing fired for any of them


def test_verify_endpoint_alerts_on_a_real_decoy_but_looks_like_a_normal_failure(client, alerts):
    r = client.get("/api/internal/verify", headers={"X-API-Key": honeytoken.generate_token()})
    assert (r.status_code, r.json()) == (401, GENERIC_401)  # identical to the bad-key answer
    assert len(alerts) == 1
    title, fields = alerts[0]
    assert title == "Honeytoken triggered"
    assert fields["Endpoint"] == "/api/internal/verify"


def test_non_ascii_signature_is_rejected_not_a_crash():
    accent, jp = chr(233), chr(0x65E5) + chr(0x672C)
    assert honeytoken.is_valid_token("eidolon_live_abc." + accent + "0" * 63) is False
    assert honeytoken.is_valid_token("eidolon_live_" + jp + "." + jp) is False
