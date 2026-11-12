import hashlib
import logging
import re
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from user_agents import parse

from database import Alert, Trap, session_scope, utc_iso, utc_now
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
from services.logging_setup import mask_ip
from services.honeytoken import TOKEN_PREFIX, generate_token, is_valid_token
from services.public_url import public_base_url
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
def create_trap(body: TrapCreateRequest, request: Request) -> TrapCreateResponse:
    # Plain `def`: FastAPI runs it in its thread pool, so the query does not block the event loop.
    trap_id = uuid.uuid4().hex[:8]
    with session_scope() as db:
        db.add(Trap(id=trap_id, name=body.name, source_type=body.source_type, context=body.context))
        db.commit()
    return TrapCreateResponse(id=trap_id, trap_url=f"{public_base_url(request)}/trap/{trap_id}")


def _visitor_fields(request: Request, referer: str | None = None) -> dict:
    """What we know at once about a visitor, as column values. The geolocation columns start as the
    same "Unknown" values a failed lookup gives; _finish_hit fills them in after the response."""
    ua = parse(request.headers.get("user-agent", ""))
    return {
        "ip": get_client_ip(request),
        **_geo_columns({}),
        "browser": f"{ua.browser.family} {ua.browser.version_string}".strip(),
        "os": ua.os.family,
        "device": ua.device.family,
        "referer": referer,
    }


def _geo_columns(geo: dict) -> dict:
    """The alert columns that come from the geolocation answer ({} = lookup failed)."""
    return {
        "location": f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}",
        "latitude": geo.get("lat", 0.0),
        "longitude": geo.get("lon", 0.0),
        "isp": geo.get("isp", "Unknown"),
        "org": geo.get("org") or None,
        "asn": geo.get("as") or None,
    }


def _trap_name(trap_id: str) -> str | None:
    """The trap's name, or None if there is no such trap. Runs in a worker thread."""
    with session_scope() as db:
        trap = db.query(Trap).filter(Trap.id == trap_id).first()
        return trap.name if trap else None


def _store_hit(trap_id: str, fields: dict, count: bool) -> int:
    """Insert the hit and, for a page load, bump the counter: one transaction. Returns the new hit's id.
    Runs in a worker thread."""
    with session_scope() as db:
        alert = Alert(trap_id=trap_id, **fields)
        db.add(alert)
        db.flush()  # assigns alert.id without ending the transaction
        hit_id = alert.id
        if count:
            count_hit(db, trap_id)
        db.commit()
        return hit_id


def _update_geo(hit_id: int, geo: dict) -> None:
    """Fill in a stored hit's location columns. Opens its own session: the request's is long gone."""
    with session_scope() as db:
        db.query(Alert).filter(Alert.id == hit_id).update(_geo_columns(geo), synchronize_session=False)
        db.commit()


async def _finish_hit(hit_id: int, ip: str, push: tuple[str, dict] | None) -> None:
    """Runs after the response has been sent: look the IP up, store the location, send the push.
    Must never raise (nobody is left to catch it), so every step is wrapped and logged by class name only.
    Not guaranteed to run: if the server stops right after the response, the hit is stored but stays
    "Unknown" and no push goes out."""
    masked = mask_ip(ip)
    geo: dict = {}
    try:
        geo = await lookup_ip(ip)
        if geo:
            await run_in_threadpool(_update_geo, hit_id, geo)
        else:
            log.info("geolocation unavailable for hit from %s", masked)
    except Exception as e:
        geo = {}
        log.warning("geolocation step failed for hit from %s: %s", masked, type(e).__name__)

    if push is None:
        return
    title, fields = push
    if geo:  # without a location the push simply leaves these two lines out
        columns = _geo_columns(geo)
        fields = {**fields, "Location": clean(columns["location"]), "ISP": clean(columns["isp"])}
    try:
        await send_ntfy_alert(title, fields)
    except Exception as e:
        log.warning("push step failed: %s", type(e).__name__)


def count_hit(db: Session, trap_id: str) -> None:
    """Add one to the trap's counter inside the database ("SET trigger_count = trigger_count + 1").
    Reading the number into Python, adding one and writing it back would lose a count when two hits
    arrive at once; this way the database does the add, one row lock at a time."""
    db.query(Trap).filter(Trap.id == trap_id).update(
        {Trap.trigger_count: Trap.trigger_count + 1}, synchronize_session=False
    )


def _page() -> HTMLResponse:
    html = _TEMPLATE_PATH.read_text(encoding="utf-8") if _TEMPLATE_PATH.exists() else _FALLBACK_HTML
    return HTMLResponse(html)


@router.get("/trap/{trap_id}", response_class=HTMLResponse)
@limiter.limit(TRAP_PAGE_LIMIT)
async def trigger_trap(trap_id: str, request: Request, background: BackgroundTasks) -> HTMLResponse:
    # Order: validate -> store the hit and count it -> claim the push slot -> answer the visitor ->
    # (in the background) geolocate, update the hit, push. Every database step is a sync helper run
    # in the thread pool, so a slow query never freezes the event loop.
    # Decide validity first, with no side effects: an id that is not a real trap gets the
    # same page but writes no row, calls no geolocation API and sends no push.
    name = await run_in_threadpool(_trap_name, trap_id)
    if name is None:
        log.info("trap page requested for an unknown id %r", clean(trap_id))
        return _page()

    # Capped: the header is visitor-controlled and can be arbitrarily long.
    referer = request.headers.get("referer", "")[:_MAX_REFERER] or None
    fields = _visitor_fields(request, referer=referer)
    hit_id = await run_in_threadpool(_store_hit, trap_id, fields, True)
    log.info("trap hit recorded", extra={"trap_id": clean(trap_id), "visitor": mask_ip(fields["ip"])})

    # Claimed here, before the response, not in the background: two hits arriving together must not
    # both find the slot free. (Claiming has no side effect beyond marking the slot taken.)
    push = None
    if should_alert(f"trap:{trap_id}"):
        push = (
            f"Trap '{name}' triggered",
            {
                "IP": clean(fields["ip"]),
                "Browser": clean(fields["browser"]),
                "OS": clean(fields["os"]),
                "Device": clean(fields["device"]),
            },
        )
    background.add_task(_finish_hit, hit_id, fields["ip"], push)
    return _page()


@router.post("/trap/{trap_id}/login", status_code=204)
@limiter.limit(TRAP_LOGIN_LIMIT)
async def trap_login_attempt(
    trap_id: str, body: TrapLoginAttempt, request: Request, background: BackgroundTasks
) -> Response:
    """Called by the fake login page when its form is submitted. Logged as its
    own hit (a page load already logged the visit), carrying the typed
    email/username as-is and only the password's length. No referrer: the
    browser sends the trap page itself here, and where the visitor really came
    from is already on the page-load hit."""
    # Same rule as the page: only a real trap's id is worth a database row and a lookup.
    if await run_in_threadpool(_trap_name, trap_id) is None:
        log.info("trap login submitted for an unknown id %r", clean(trap_id))
        return Response(status_code=204)

    fields = _visitor_fields(request)
    fields.update(
        email=body.email or None,
        password_attempted=body.password_length > 0,
        password_length=body.password_length,
    )
    hit_id = await run_in_threadpool(_store_hit, trap_id, fields, False)
    log.info("trap login hit recorded", extra={"trap_id": clean(trap_id), "visitor": mask_ip(fields["ip"])})
    background.add_task(_finish_hit, hit_id, fields["ip"], None)  # logins never push
    return Response(status_code=204)


@router.post(
    "/api/findings/{finding_id}/deploy-trap",
    response_model=TrapCreateResponse,
    dependencies=[Depends(require_admin)],
)
def deploy_trap_for_finding(
    finding_id: str, body: FindingTrapRequest, request: Request
) -> TrapCreateResponse:
    """Owner-only: turn a repo-scan secret finding into a real trap, named from
    the finding's own context. Idempotent - a finding already trapped (e.g. a
    rescan, or a second click) returns the existing trap instead of a duplicate."""
    base = public_base_url(request)
    with session_scope() as db:
        existing = db.query(Trap).filter(Trap.finding_id == finding_id).first()
        if existing:
            return TrapCreateResponse(id=existing.id, trap_url=f"{base}/trap/{existing.id}")

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
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.query(Trap).filter(Trap.finding_id == finding_id).first()
            if existing is None:
                raise
            trap_id = existing.id
    return TrapCreateResponse(id=trap_id, trap_url=f"{base}/trap/{trap_id}")


@router.delete("/api/traps/{trap_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_trap(trap_id: str) -> Response:
    """Owner-only cleanup for a trap that shouldn't exist (e.g. one created
    from a broken/placeholder finding). Its alert history goes with it -
    there is nothing left worth keeping once the trap itself is gone."""
    with session_scope() as db:
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
    return HoneytokenResponse(token=generate_token(), base_url=public_base_url(request))


@router.post(
    "/api/findings/{finding_id}/deploy-decoy",
    response_model=HoneytokenResponse,
    dependencies=[Depends(require_admin)],
)
async def deploy_decoy(finding_id: str, request: Request) -> HoneytokenResponse:
    return HoneytokenResponse(
        token=generate_token(finding_id), base_url=public_base_url(request)
    )


# Not admin-gated on purpose: it has to look like an ordinary public "is my key valid" endpoint.
# Nothing in this repo calls it; whoever holds a stolen decoy key would. So it is rate limited per IP.
@router.get("/api/internal/verify")
@limiter.limit(VERIFY_LIMIT)
async def verify_key(request: Request) -> JSONResponse:
    """Looks like a real "is my API key still valid" endpoint. A decoy key
    never gets a real answer - hitting it at all is the signal, so match or
    no match, the caller always sees the same generic auth failure.

    The token is self-verifying (HMAC signature, no DB lookup) and the
    ntfy notification sent below is the only durable record of a trigger -
    Render's free tier wipes local disk on restart, so nothing here counts
    on state surviving between requests.
    """
    key = _extract_key(request)
    background = BackgroundTasks()
    if not is_valid_token(key):
        log.info("honeytoken verify called with a key that does not verify")  # never log the key itself
    else:
        ip = get_client_ip(request)
        # One push per key per window (a hash, so the key itself is never stored).
        if should_alert("token:" + hashlib.sha256(key.encode()).hexdigest()[:16]):
            finding_id = key[len(TOKEN_PREFIX):].rpartition(".")[0].partition(":")[2]
            background.add_task(_alert_honeytoken, ip, finding_id)

    return JSONResponse(status_code=401, content=_INVALID_KEY_ERROR, background=background)


async def _alert_honeytoken(ip: str, finding_id: str) -> None:
    geo = await lookup_ip(ip)
    await send_ntfy_alert(
        "Honeytoken triggered",
        {
            "Timestamp": utc_iso(utc_now()),
            "IP": clean(ip),
            "Location": clean(f"{geo.get('city', 'Unknown')}, {geo.get('country', 'Unknown')}"),
            "Endpoint": "/api/internal/verify",
            **({"Finding": clean(finding_id)} if finding_id else {}),
        },
    )


@router.get("/api/traps/alerts", response_model=list[AlertResponse], dependencies=[Depends(require_admin)])
def list_alerts() -> list[AlertResponse]:
    with session_scope() as db:
        rows = (
            db.query(Alert, Trap)
            .outerjoin(Trap, Alert.trap_id == Trap.id)
            .order_by(Alert.timestamp.desc())
            .limit(50)
            .all()
        )
        return _to_responses(rows)  # built while the session is still open


def _to_responses(rows) -> list[AlertResponse]:
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
