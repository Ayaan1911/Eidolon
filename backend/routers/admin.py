from fastapi import APIRouter, Depends, HTTPException, Request

from models.schemas import AdminLoginRequest, AdminLoginResponse
from routers.exposure import limiter
from services.admin_auth import issue_token, passphrase_matches, require_admin
from services.client_ip import get_client_ip, socket_peer, trusted_proxy_hops

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Per client IP (see services/client_ip.py), so one guesser cannot lock out the others.
ADMIN_LOGIN_LIMIT = "5/minute"


@router.post("/login", response_model=AdminLoginResponse)
@limiter.limit(ADMIN_LOGIN_LIMIT)
async def admin_login(request: Request, body: AdminLoginRequest) -> AdminLoginResponse:
    # Deliberately generic: nothing about why a login failed (wrong passphrase,
    # ADMIN_KEY unset) is ever reported back.
    if not passphrase_matches(body.passphrase):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token, expires_at = issue_token()
    return AdminLoginResponse(token=token, expires_at=expires_at)


# Proxy headers worth looking at when working out how many proxies sit in front of the app.
_PROXY_HEADERS = ["x-forwarded-for", "x-real-ip", "cf-connecting-ip", "true-client-ip", "forwarded", "via"]


@router.get("/diagnostics/client-ip", dependencies=[Depends(require_admin)])
async def client_ip_diagnostics(request: Request) -> dict:
    """Admin-only: what this request looks like to the app, so TRUSTED_PROXY_HOPS can be
    chosen by comparing the resolved IP with your real one. Only headers, no secrets."""
    return {
        "socket_peer": socket_peer(request),
        "headers": {name: request.headers.get(name) for name in _PROXY_HEADERS if request.headers.get(name)},
        "trusted_proxy_hops": trusted_proxy_hops(),
        "resolved_ip": get_client_ip(request),
    }
