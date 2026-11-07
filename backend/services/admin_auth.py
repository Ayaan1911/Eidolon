"""Stateless admin sessions for the Trap Lab.

Same idea as the honeytoken: the token carries its own expiry and an HMAC
signature, so verifying is a recompute - no database, no session store, and it
survives Render's free-tier restarts.

Key separation: tokens are NOT signed with HONEYTOKEN_SECRET itself (that key signs
the public decoy keys), nor with the passphrase (a human-chosen passphrase could be
guessed offline from a captured token). The signing key is derived from both with a
labelled HMAC, so rotating either secret revokes every token already issued.
"""

import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request


TOKEN_PREFIX = "eidolon_admin_"
TOKEN_TTL_SECONDS = 24 * 60 * 60
# Fixed label so the derived key can never equal a key used for anything else.
SIGNING_KEY_LABEL = b"eidolon/admin-session/v1"


def passphrase_matches(candidate: str) -> bool:
    expected = os.environ.get("ADMIN_KEY", "")
    if not expected:
        return False
    # Hash both sides first so compare_digest sees equal-length inputs: the time taken
    # then says nothing about the real passphrase's length.
    return hmac.compare_digest(
        hashlib.sha256(candidate.encode()).digest(), hashlib.sha256(expected.encode()).digest()
    )


def _signing_key() -> bytes:
    """Derived from both secrets; KeyError if either is missing, ValueError if either is blank."""
    admin_key = os.environ["ADMIN_KEY"]
    honeytoken_secret = os.environ["HONEYTOKEN_SECRET"]
    if not admin_key or not honeytoken_secret:
        raise ValueError("secrets not configured")  # never sign or verify with an empty key
    return hmac.new(honeytoken_secret.encode(), SIGNING_KEY_LABEL + b":" + admin_key.encode(), hashlib.sha256).digest()


def _signature(expires_at: int) -> str:
    return hmac.new(_signing_key(), f"admin:{expires_at}".encode(), hashlib.sha256).hexdigest()


def issue_token(now: float | None = None) -> tuple[str, int]:
    expires_at = int(time.time() if now is None else now) + TOKEN_TTL_SECONDS
    return f"{TOKEN_PREFIX}{expires_at}.{_signature(expires_at)}", expires_at


def is_valid_admin_token(token: str | None, now: float | None = None) -> bool:
    if not token or not token.startswith(TOKEN_PREFIX):
        return False
    expiry, sep, sig = token[len(TOKEN_PREFIX) :].rpartition(".")
    if not sep or not expiry.isdigit():
        return False
    try:
        expected = _signature(int(expiry))
    except (KeyError, ValueError):  # ADMIN_KEY or HONEYTOKEN_SECRET missing or blank
        return False
    if not hmac.compare_digest(sig.encode(), expected.encode()):
        return False
    return int(expiry) > (time.time() if now is None else now)


def is_admin_request(request: Request) -> bool:
    """True if the request carries a valid admin bearer token. Non-raising, for
    endpoints (like the public repo scan) that behave differently for an admin
    caller but must still work for everyone else."""
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    return scheme.lower() == "bearer" and is_valid_admin_token(token.strip())


def require_admin(request: Request) -> None:
    """FastAPI dependency: 401 unless a valid admin token is in the Authorization header."""
    if not is_admin_request(request):
        raise HTTPException(status_code=401, detail="Unauthorized")
