import httpx

IP_API_BASE = "http://ip-api.com/json"


async def lookup_ip(ip: str) -> dict:
    """Best-effort IP geolocation. Never raises — a failed or rate-limited
    lookup should not stop a trap from logging the visitor and serving its page."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{IP_API_BASE}/{ip}")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return {}
    return {} if data.get("status") == "fail" else data
