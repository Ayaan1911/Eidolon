from urllib.parse import quote

import httpx

from models.schemas import BreachData, EmailCheckResponse

XPOSED_API_BASE = "https://api.xposedornot.com/v1"

# ponytail: in-memory cache, single-process only — move to Redis/TTL if run with multiple workers
_metadata_cache: dict[str, dict] = {}


class BreachCheckError(Exception):
    """Raised when the breach provider fails. The message is constant and public: it never holds the email or provider text."""

PUBLIC_ERROR = "The breach lookup service is unavailable right now. Try again later."


async def _get_breach_metadata(client: httpx.AsyncClient) -> dict[str, dict]:
    if _metadata_cache:
        return _metadata_cache
    resp = await client.get(f"{XPOSED_API_BASE}/breaches", timeout=10.0)
    resp.raise_for_status()
    for b in resp.json().get("exposedBreaches", []):
        _metadata_cache[b["breachID"]] = b
    return _metadata_cache


async def _get_breach_names(client: httpx.AsyncClient, email: str) -> list[str]:
    resp = await client.get(f"{XPOSED_API_BASE}/check-email/{quote(email, safe='')}", timeout=10.0)
    if resp.status_code == 404:
        return []
    resp.raise_for_status()
    raw = resp.json().get("breaches", [])
    if not raw:
        return []
    # API wraps the name list in an extra list: {"breaches": [["Name1", "Name2", ...]]}
    return raw[0] if isinstance(raw[0], list) else raw


def _severity(meta: dict, exposed: list[str]) -> str:
    if meta.get("passwordRisk") in ("plaintext", "easytocrack"):
        return "High"
    text = " ".join(exposed).lower()
    if any(k in text for k in ("password", "ssn", "social security", "credit card", "financial")):
        return "High"
    return "Medium"


async def check_email_exposure(email: str) -> EmailCheckResponse:
    async with httpx.AsyncClient() as client:
        try:
            names = await _get_breach_names(client, email)
            metadata = await _get_breach_metadata(client) if names else {}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            # from None: the original error's text holds the request URL, and the URL holds the email.
            raise BreachCheckError(PUBLIC_ERROR) from None

    breaches = []
    for name in names:
        meta = metadata.get(name, {})
        date = str(meta.get("breachedDate", "Unknown")).split("T")[0]
        exposed = [x for x in meta.get("exposedData", ["Email addresses"]) if x][:5]
        breaches.append(
            BreachData(name=name, date=date, severity=_severity(meta, exposed), data_exposed=exposed)
        )

    return EmailCheckResponse(
        email=email,
        total_breaches=len(breaches),
        breaches=breaches,
    )
