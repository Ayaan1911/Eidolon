import math

import httpx

# Free, no key, HTTPS (1,000 lookups/day per client IP; no uptime guarantee, so a failure is expected and fine).
GEO_API_BASE = "https://ipwho.is"


def _text(value: object) -> str | None:
    return value.strip()[:100] if isinstance(value, str) and value.strip() else None


def _coord(value: object, limit: float) -> float | None:
    ok = isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    return float(value) if ok and abs(value) <= limit else None


def _clean(data: object) -> dict:
    """Map the provider's reply to the keys the trap code reads (city, country, lat, lon, isp, org, as).
    Anything missing or of the wrong type is simply left out."""
    if not isinstance(data, dict) or data.get("success") is not True:
        return {}
    conn = data.get("connection") if isinstance(data.get("connection"), dict) else {}
    asn, org = conn.get("asn"), _text(conn.get("org"))
    out = {
        "city": _text(data.get("city")),
        "country": _text(data.get("country")),
        "lat": _coord(data.get("latitude"), 90),
        "lon": _coord(data.get("longitude"), 180),
        "isp": _text(conn.get("isp")),
        "org": org,
        "as": f"AS{asn} {org or ''}".strip() if isinstance(asn, int) and not isinstance(asn, bool) else None,
    }
    return {k: v for k, v in out.items() if v is not None}


async def lookup_ip(ip: str) -> dict:
    """Best-effort IP geolocation. Never raises: a failed, rate-limited or malformed reply
    must not stop a trap from logging the visitor and serving its page."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{GEO_API_BASE}/{ip}")
            resp.raise_for_status()
            return _clean(resp.json())
    except (httpx.HTTPError, ValueError):  # ValueError: the reply was not JSON
        return {}
