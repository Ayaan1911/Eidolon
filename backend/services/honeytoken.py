"""Self-verifying decoy API keys.

The token encodes a random nonce plus an HMAC signature over that nonce, keyed
by HONEYTOKEN_SECRET. Verifying just recomputes the signature - no database
lookup involved, so it keeps working after Render's free tier wipes the
filesystem on a restart or idle spin-down.
"""

import hashlib
import hmac
import os
import secrets

TOKEN_PREFIX = "eidolon_live_"


def _secret() -> bytes:
    return os.environ["HONEYTOKEN_SECRET"].encode()


def _sign(nonce: str) -> str:
    return hmac.new(_secret(), nonce.encode(), hashlib.sha256).hexdigest()


def generate_token() -> str:
    nonce = secrets.token_hex(16)
    return f"{TOKEN_PREFIX}{nonce}.{_sign(nonce)}"


def is_valid_token(token: str | None) -> bool:
    if not token or not token.startswith(TOKEN_PREFIX):
        return False
    nonce, _, sig = token[len(TOKEN_PREFIX) :].partition(".")
    if not sig:
        return False
    try:
        expected = _sign(nonce)
    except KeyError:
        return False
    return hmac.compare_digest(sig, expected)
