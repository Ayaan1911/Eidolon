import httpx

from models.schemas import BreachData, EmailCheckResponse

XPOSED_API_BASE = "https://api.xposedornot.com/v1"

# ponytail: in-memory cache, single-process only — move to Redis/TTL if run with multiple workers
_metadata_cache: dict[str, dict] = {}


class BreachCheckError(Exception):
    """Raised when the XposedOrNot API cannot be reached or returns an unexpected error."""


async def _get_breach_metadata(client: httpx.AsyncClient) -> dict[str, dict]:
    if _metadata_cache:
        return _metadata_cache
    resp = await client.get(f"{XPOSED_API_BASE}/breaches", timeout=10.0)
    resp.raise_for_status()
    for b in resp.json().get("exposedBreaches", []):
        _metadata_cache[b["breachID"]] = b
    return _metadata_cache


async def _get_breach_names(client: httpx.AsyncClient, email: str) -> list[str]:
    resp = await client.get(f"{XPOSED_API_BASE}/check-email/{email}", timeout=10.0)
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


def _risk_score(breaches: list[BreachData]) -> int:
    if not breaches:
        return 0
    score = min(100, 20 + len(breaches) * 15)
    if any(b.severity == "High" for b in breaches):
        score = max(score, 85)
    return score


async def check_email_exposure(email: str) -> EmailCheckResponse:
    async with httpx.AsyncClient() as client:
        try:
            names = await _get_breach_names(client, email)
            metadata = await _get_breach_metadata(client) if names else {}
        except httpx.HTTPError as e:
            raise BreachCheckError(f"XposedOrNot API request failed: {e}") from e

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
        risk_score=_risk_score(breaches),
        total_breaches=len(breaches),
        breaches=breaches,
    )
