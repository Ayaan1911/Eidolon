import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session
from user_agents import parse

from database import Alert, Trap, get_db
from models.schemas import (
    AlertResponse,
    HoneytokenResponse,
    TrapCreateRequest,
    TrapCreateResponse,
    TrapLoginAttempt,
)
from services.admin_auth import require_admin
from services.geolocation import lookup_ip
from services.honeytoken import generate_token, is_valid_token
from services.ntfy_alert import send_ntfy_alert

router = APIRouter(tags=["traps"])

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "fake_login.html"
_FALLBACK_HTML = "<html><body><h1>Admin Login</h1><p>System Maintenance</p></body></html>"

_INVALID_KEY_ERROR = {"detail": "Invalid or expired API key"}
_MAX_REFERER = 500


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
    ip = request.client.host if request.client else "unknown"
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


@router.get("/trap/{trap_id}", response_class=HTMLResponse)
async def trigger_trap(trap_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    trap = db.query(Trap).filter(Trap.id == trap_id).first()
    trap_name = trap.name if trap else trap_id

    # Capped: the header is visitor-controlled and can be arbitrarily long.
    referer = request.headers.get("referer", "")[:_MAX_REFERER] or None
    alert = await _record_hit(db, request, trap_id, referer=referer)
    if trap:
        trap.trigger_count += 1
    db.commit()

    await send_ntfy_alert(
        f"Trap '{trap_name}' triggered",
        {
            "IP": alert.ip,
            "Location": alert.location,
            "ISP": alert.isp,
            "Browser": alert.browser,
            "OS": alert.os,
            "Device": alert.device,
        },
    )

    html = _TEMPLATE_PATH.read_text(encoding="utf-8") if _TEMPLATE_PATH.exists() else _FALLBACK_HTML
    return HTMLResponse(html)


@router.post("/trap/{trap_id}/login", status_code=204)
async def trap_login_attempt(
    trap_id: str, body: TrapLoginAttempt, request: Request, db: Session = Depends(get_db)
) -> Response:
    """Called by the fake login page when its form is submitted. Logged as its
    own hit (a page load already logged the visit), carrying the typed
    email/username as-is and only the password's length. No referrer: the
    browser sends the trap page itself here, and where the visitor really came
    from is already on the page-load hit."""
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


@router.post("/api/traps/honeytoken", response_model=HoneytokenResponse)
async def create_honeytoken(request: Request) -> HoneytokenResponse:
    return HoneytokenResponse(token=generate_token(), base_url=str(request.base_url).rstrip("/"))


@router.post("/api/findings/{finding_id}/deploy-decoy", response_model=HoneytokenResponse)
async def deploy_decoy(finding_id: str, request: Request) -> HoneytokenResponse:
    return HoneytokenResponse(
        token=generate_token(finding_id), base_url=str(request.base_url).rstrip("/")
    )


@router.get("/api/internal/verify")
async def verify_key(request: Request) -> None:
    """Looks like a real "is my API key still valid" endpoint. A decoy key
    never gets a real answer - hitting it at all is the signal, so match or
    no match, the caller always sees the same generic auth failure.

    The token is self-verifying (HMAC signature, no DB lookup) and the
    ntfy notification sent below is the only durable record of a trigger -
    Render's free tier wipes local disk on restart, so nothing here counts
    on state surviving between requests.
    """
    if is_valid_token(_extract_key(request)):
        ip = request.client.host if request.client else "unknown"
        geo = await lookup_ip(ip)
        await send_ntfy_alert(
            "Honeytoken triggered",
            {
                "Timestamp": datetime.utcnow().isoformat() + "Z",
                "IP": ip,
                "Location": f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}",
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
            timestamp=a.timestamp.isoformat(),
            source_type=t.source_type if t else None,
            context=t.context if t else None,
        )
        for a, t in rows
    ]
