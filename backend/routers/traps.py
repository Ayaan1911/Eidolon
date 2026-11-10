import hashlib
import logging
import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from user_agents import parse

from database import Alert, Trap, get_db, utc_iso, utc_now
from models.schemas import (
    AlertResponse,
    FindingTrapRequest,
    HoneytokenResponse,
    TrapCreateRequest,
    TrapCreateResponse,
    TrapLoginAttempt,
)
from routers.exposure import limiter
from services.admin_auth import require_admin
from services.client_ip import get_client_ip
from services.geolocation import lookup_ip
from services.honeytoken import generate_token, is_valid_token
from services.ntfy_alert import send_ntfy_alert

router = APIRouter(tags=["traps"])

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "fake_login.html"
_FALLBACK_HTML = "<html><body><h1>Admin Login</h1><p>System Maintenance</p></body></html>"

_INVALID_KEY_ERROR = {"detail": "Invalid or expired API key"}
_MAX_REFERER = 500

# Per client IP. Trap pages are public by design, so they get limits instead of a login.
TRAP_PAGE_LIMIT = "30/minute"
TRAP_LOGIN_LIMIT = "10/minute"
VERIFY_LIMIT = "30/minute"

# At most one ntfy push per trap per window; repeat hits are still logged and counted.
# In memory, so it resets when the server restarts - acceptable: the worst case is one extra push.
ALERT_WINDOW_SECONDS = 5 * 60
_last_alert_at: dict[str, float] = {}

log = logging.getLogger("eidolon.traps")

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_MAX_LOGGED = 80


def clean(value: object, limit: int = _MAX_LOGGED) -> str:
    """Make visitor-controlled text safe for logs and the ntfy body: no line breaks or
    control characters (so nobody can forge extra log lines or alert fields), and capped."""
    return _CONTROL_CHARS.sub(" ", str(value))[:limit]


def should_alert(key: str) -> bool:
    """True if no push went out for this key in the last ALERT_WINDOW_SECONDS (and notes this one)."""
    now = time.monotonic()
    last = _last_alert_at.get(key)
    if last is not None and now - last < ALERT_WINDOW_SECONDS:
        return False
    if len(_last_alert_at) > 1000:  # keep the dict small: forget keys whose window has passed
        for k in [k for k, t in _last_alert_at.items() if now - t >= ALERT_WINDOW_SECONDS]:
            del _last_alert_at[k]
    _last_alert_at[key] = now
    return True


def _extract_key(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key")


@router.post("/api/traps", response_model=TrapCreateResponse, dependencies=[Depends(require_admin)])
async def create_trap(
    body: TrapCreateRequest, request: Request, db: Session = Depends(get_db)
) -> TrapCreateResponse:
    trap_id = uuid.uuid4().hex[:8]
    db.add(Trap(id=trap_id, name=body.name, source_type=body.source_type, context=body.context))
    db.commit()
    return TrapCreateResponse(id=trap_id, trap_url=f"{request.base_url}trap/{trap_id}")


async def _record_hit(
    db: Session, request: Request, trap_id: str, referer: str | None = None, **login_fields
) -> Alert:
    """Log one visitor hit with the network/browser context shared by page
    loads and login submissions. login_fields are set only for the latter."""
    ip = get_client_ip(request)
    geo = await lookup_ip(ip)
    ua = parse(request.headers.get("user-agent", ""))

    alert = Alert(
        trap_id=trap_id,
        ip=ip,
        location=f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}",
        latitude=geo.get("lat", 0.0),
        longitude=geo.get("lon", 0.0),
        isp=geo.get("isp", "Unknown"),
        org=geo.get("org") or None,
        asn=geo.get("as") or None,
        browser=f"{ua.browser.family} {ua.browser.version_string}".strip(),
        os=ua.os.family,
        device=ua.device.family,
        referer=referer,
        **login_fields,
    )
    db.add(alert)
    return alert


def _page() -> HTMLResponse:
    html = _TEMPLATE_PATH.read_text(encoding="utf-8") if _TEMPLATE_PATH.exists() else _FALLBACK_HTML
    return HTMLResponse(html)


@router.get("/trap/{trap_id}", response_class=HTMLResponse)
@limiter.limit(TRAP_PAGE_LIMIT)
async def trigger_trap(trap_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    # Decide validity first, with no side effects: an id that is not a real trap gets the
    # same page but writes no row, calls no geolocation API and sends no push.
    trap = db.query(Trap).filter(Trap.id == trap_id).first()
    if not trap:
        log.info("trap page requested for an unknown id %r", clean(trap_id))
        return _page()

    # Capped: the header is visitor-controlled and can be arbitrarily long.
    referer = request.headers.get("referer", "")[:_MAX_REFERER] or None
    alert = await _record_hit(db, request, trap_id, referer=referer)
    trap.trigger_count += 1
    db.commit()

    if should_alert(f"trap:{trap.id}"):
        await send_ntfy_alert(
            f"Trap '{trap.name}' triggered",
            {
                "IP": clean(alert.ip),
                "Location": clean(alert.location),
                "ISP": clean(alert.isp),
                "Browser": clean(alert.browser),
                "OS": clean(alert.os),
                "Device": clean(alert.device),
            },
        )
    return _page()


@router.post("/trap/{trap_id}/login", status_code=204)
@limiter.limit(TRAP_LOGIN_LIMIT)
async def trap_login_attempt(
    trap_id: str, body: TrapLoginAttempt, request: Request, db: Session = Depends(get_db)
) -> Response:
    """Called by the fake login page when its form is submitted. Logged as its
    own hit (a page load already logged the visit), carrying the typed
    email/username as-is and only the password's length. No referrer: the
    browser sends the trap page itself here, and where the visitor really came
    from is already on the page-load hit."""
    # Same rule as the page: only a real trap's id is worth a database row and a lookup.
    if not db.query(Trap).filter(Trap.id == trap_id).first():
        log.info("trap login submitted for an unknown id %r", clean(trap_id))
        return Response(status_code=204)

    await _record_hit(
        db,
        request,
        trap_id,
        email=body.email or None,
        password_attempted=body.password_length > 0,
        password_length=body.password_length,
    )
    db.commit()
    return Response(status_code=204)


@router.post(
    "/api/findings/{finding_id}/deploy-trap",
    response_model=TrapCreateResponse,
    dependencies=[Depends(require_admin)],
)
async def deploy_trap_for_finding(
    finding_id: str, body: FindingTrapRequest, request: Request, db: Session = Depends(get_db)
) -> TrapCreateResponse:
    """Owner-only: turn a repo-scan secret finding into a real trap, named from
    the finding's own context. Idempotent - a finding already trapped (e.g. a
    rescan, or a second click) returns the existing trap instead of a duplicate."""
    existing = db.query(Trap).filter(Trap.finding_id == finding_id).first()
    if existing:
        return TrapCreateResponse(id=existing.id, trap_url=f"{request.base_url}trap/{existing.id}")

    trap_id = uuid.uuid4().hex[:8]
    db.add(
        Trap(
            id=trap_id,
            name=f"Secret canary — {body.type} in {body.repo}/{body.file}",
            source_type="secret",
            context=f"{body.repo}:{body.file}",
            finding_id=finding_id,
        )
    )
    db.commit()
    return TrapCreateResponse(id=trap_id, trap_url=f"{request.base_url}trap/{trap_id}")


@router.delete("/api/traps/{trap_id}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_trap(trap_id: str, db: Session = Depends(get_db)) -> Response:
    """Owner-only cleanup for a trap that shouldn't exist (e.g. one created
    from a broken/placeholder finding). Its alert history goes with it -
    there is nothing left worth keeping once the trap itself is gone."""
    trap = db.query(Trap).filter(Trap.id == trap_id).first()
    if not trap:
        raise HTTPException(status_code=404, detail="No such trap")
    db.query(Alert).filter(Alert.trap_id == trap_id).delete()
    db.delete(trap)
    db.commit()
    return Response(status_code=204)


# Minting a decoy key is a Trap Lab action, so it needs the admin session like the rest of Trap Lab.
@router.post(
    "/api/traps/honeytoken", response_model=HoneytokenResponse, dependencies=[Depends(require_admin)]
)
async def create_honeytoken(request: Request) -> HoneytokenResponse:
    return HoneytokenResponse(token=generate_token(), base_url=str(request.base_url).rstrip("/"))


@router.post(
    "/api/findings/{finding_id}/deploy-decoy",
    response_model=HoneytokenResponse,
    dependencies=[Depends(require_admin)],
)
async def deploy_decoy(finding_id: str, request: Request) -> HoneytokenResponse:
    return HoneytokenResponse(
        token=generate_token(finding_id), base_url=str(request.base_url).rstrip("/")
    )


# Not admin-gated on purpose: it has to look like an ordinary public "is my key valid" endpoint.
# Nothing in this repo calls it; whoever holds a stolen decoy key would. So it is rate limited per IP.
@router.get("/api/internal/verify")
@limiter.limit(VERIFY_LIMIT)
async def verify_key(request: Request) -> None:
    """Looks like a real "is my API key still valid" endpoint. A decoy key
    never gets a real answer - hitting it at all is the signal, so match or
    no match, the caller always sees the same generic auth failure.

    The token is self-verifying (HMAC signature, no DB lookup) and the
    ntfy notification sent below is the only durable record of a trigger -
    Render's free tier wipes local disk on restart, so nothing here counts
    on state surviving between requests.
    """
    key = _extract_key(request)
    if not is_valid_token(key):
        log.info("honeytoken verify called with a key that does not verify")  # never log the key itself
    else:
        ip = get_client_ip(request)
        # One push per key per window (a hash, so the key itself is never stored).
        if should_alert("token:" + hashlib.sha256(key.encode()).hexdigest()[:16]):
            geo = await lookup_ip(ip)
            await send_ntfy_alert(
                "Honeytoken triggered",
                {
                    "Timestamp": utc_iso(utc_now()),
                    "IP": clean(ip),
                    "Location": clean(f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}"),
                    "Endpoint": "/api/internal/verify",
                },
            )

    raise HTTPException(status_code=401, detail=_INVALID_KEY_ERROR["detail"])


@router.get("/api/traps/alerts", response_model=list[AlertResponse], dependencies=[Depends(require_admin)])
async def list_alerts(db: Session = Depends(get_db)) -> list[AlertResponse]:
    rows = (
        db.query(Alert, Trap)
        .outerjoin(Trap, Alert.trap_id == Trap.id)
        .order_by(Alert.timestamp.desc())
        .limit(50)
        .all()
    )
    return [
        AlertResponse(
            id=a.id,
            trap_id=a.trap_id,
            ip=a.ip,
            location=a.location,
            lat=a.latitude,
            lng=a.longitude,
            isp=a.isp,
            org=a.org,
            asn=a.asn,
            browser=a.browser,
            os=a.os,
            device=a.device,
            referer=a.referer,
            email=a.email,
            password_attempted=a.password_attempted,
            password_length=a.password_length,
            timestamp=utc_iso(a.timestamp),
            source_type=t.source_type if t else None,
            context=t.context if t else None,
        )
        for a, t in rows
    ]
