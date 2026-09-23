"""Stateless admin sessions for the Trap Lab.

Same idea as the honeytoken: the token carries its own expiry and an HMAC
signature, so verifying is a recompute - no database, no session store, and it
survives Render's free-tier restarts. ADMIN_KEY is folded into the signed
message, so rotating (or unsetting) it revokes every token already issued.
The "admin:" prefix keeps these signatures apart from honeytoken ones, whose
payloads always start with a hex nonce.
"""

import hmac
import os
import time

from fastapi import HTTPException, Request

from services.honeytoken import sign

TOKEN_PREFIX = "eidolon_admin_"
TOKEN_TTL_SECONDS = 24 * 60 * 60


def passphrase_matches(candidate: str) -> bool:
    expected = os.environ.get("ADMIN_KEY", "")
    return bool(expected) and hmac.compare_digest(candidate.encode(), expected.encode())


def _signature(expires_at: int) -> str:
    return sign(f"admin:{expires_at}:{os.environ['ADMIN_KEY']}")


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
    except KeyError:  # ADMIN_KEY or HONEYTOKEN_SECRET not configured
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
