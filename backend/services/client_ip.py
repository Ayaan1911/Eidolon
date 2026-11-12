"""The one place that decides which IP address a request "comes from".

Used for rate limiting and for the IP stored in trap alerts, so both agree.

X-Forwarded-For is a header any client can send. Behind a proxy it looks like
"<whatever the client claimed>, <added by proxy 1>, <added by proxy 2>": each proxy
appends the address it saw to the RIGHT. So only the entries nearest the right end were
written by proxies we control; anything on the left may be forged. That is why this
counts from the right and never reads the leftmost entry.
"""

import ipaddress
import os

from fastapi import Request

# How many reverse proxies sit between the internet and this app (Render's, ...).
# 0 = none: ignore X-Forwarded-For entirely and use the socket's peer address.
TRUSTED_PROXY_HOPS_ENV = "TRUSTED_PROXY_HOPS"
MAX_TRUSTED_PROXY_HOPS = 10  # a sanity limit; real setups use 1 or 2


def trusted_proxy_hops() -> int:
    """TRUSTED_PROXY_HOPS as a small non-negative integer (default 0), or ValueError."""
    raw = os.environ.get(TRUSTED_PROXY_HOPS_ENV, "").strip()
    if not raw:
        return 0
    if not raw.isdigit() or int(raw) > MAX_TRUSTED_PROXY_HOPS:
        raise ValueError(f"{TRUSTED_PROXY_HOPS_ENV} must be a whole number from 0 to {MAX_TRUSTED_PROXY_HOPS}")
    return int(raw)


def socket_peer(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def get_client_ip(request: Request) -> str:
    peer = socket_peer(request)
    if os.environ.get("RENDER") == "true":
        # Render's Cloudflare edge overwrites this header; X-Forwarded-For can retain forged entries.
        try:
            return str(ipaddress.ip_address(request.headers.get("cf-connecting-ip", "")))
        except ValueError:
            return peer
    hops = trusted_proxy_hops()
    if hops == 0:
        return peer

    entries = [e.strip() for e in request.headers.get("x-forwarded-for", "").split(",")]
    if len(entries) < hops:
        return peer  # fewer proxies than expected: the header is not what we were told to trust
    chosen = entries[-hops]  # 1 = the last entry, 2 = the one before it, ...
    try:
        return str(ipaddress.ip_address(chosen))
    except ValueError:
        return peer  # not an IP address at all: do not trust it
