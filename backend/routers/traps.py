import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from user_agents import parse

from database import Alert, Trap, get_db
from models.schemas import AlertResponse, TrapCreateRequest, TrapCreateResponse
from services.geolocation import lookup_ip
from services.telegram_alert import send_trap_alert

router = APIRouter(tags=["traps"])

_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "templates" / "fake_login.html"
_FALLBACK_HTML = "<html><body><h1>Admin Login</h1><p>System Maintenance</p></body></html>"


@router.post("/api/traps", response_model=TrapCreateResponse)
async def create_trap(
    body: TrapCreateRequest, request: Request, db: Session = Depends(get_db)
) -> TrapCreateResponse:
    trap_id = uuid.uuid4().hex[:8]
    db.add(Trap(id=trap_id, name=body.name))
    db.commit()
    return TrapCreateResponse(id=trap_id, trap_url=f"{request.base_url}trap/{trap_id}")


@router.get("/trap/{trap_id}", response_class=HTMLResponse)
async def trigger_trap(trap_id: str, request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    trap = db.query(Trap).filter(Trap.id == trap_id).first()
    trap_name = trap.name if trap else trap_id

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
        browser=f"{ua.browser.family} {ua.browser.version_string}".strip(),
        os=ua.os.family,
        device=ua.device.family,
    )
    db.add(alert)
    if trap:
        trap.trigger_count += 1
    db.commit()

    await send_trap_alert(
        trap_name,
        {
            "ip": alert.ip,
            "location": alert.location,
            "isp": alert.isp,
            "browser": alert.browser,
            "os": alert.os,
            "device": alert.device,
        },
    )

    html = _TEMPLATE_PATH.read_text(encoding="utf-8") if _TEMPLATE_PATH.exists() else _FALLBACK_HTML
    return HTMLResponse(html)


@router.get("/api/traps/alerts", response_model=list[AlertResponse])
async def list_alerts(db: Session = Depends(get_db)) -> list[AlertResponse]:
    alerts = db.query(Alert).order_by(Alert.timestamp.desc()).limit(50).all()
    return [
        AlertResponse(
            id=a.id,
            trap_id=a.trap_id,
            ip=a.ip,
            location=a.location,
            lat=a.latitude,
            lng=a.longitude,
            isp=a.isp,
            browser=a.browser,
            os=a.os,
            device=a.device,
            timestamp=a.timestamp.isoformat(),
        )
        for a in alerts
    ]
