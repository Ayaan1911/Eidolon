"""Self-verifying decoy API keys.

The token encodes a random nonce (optionally paired with the finding it was
deployed for) plus an HMAC signature over that payload, keyed by
HONEYTOKEN_SECRET. Verifying just recomputes the signature - no database
lookup involved, so it keeps working after Render's free tier wipes the
filesystem on a restart or idle spin-down. The finding link lives inside the
token itself rather than a DB row for the same reason.
"""

import hashlib
import hmac
import os
import secrets

TOKEN_PREFIX = "eidolon_live_"


def _secret() -> bytes:
    return os.environ["HONEYTOKEN_SECRET"].encode()


def sign(payload: str) -> str:
    return hmac.new(_secret(), payload.encode(), hashlib.sha256).hexdigest()


def generate_token(finding_id: str | None = None) -> str:
    nonce = secrets.token_hex(16)
    payload = f"{nonce}:{finding_id}" if finding_id else nonce
    return f"{TOKEN_PREFIX}{payload}.{sign(payload)}"


def is_valid_token(token: str | None) -> bool:
    if not token or not token.startswith(TOKEN_PREFIX):
        return False
    payload, sep, sig = token[len(TOKEN_PREFIX) :].rpartition(".")
    if not sep or not sig:
        return False
    try:
        expected = sign(payload)
    except KeyError:
        return False
    return hmac.compare_digest(sig, expected)
