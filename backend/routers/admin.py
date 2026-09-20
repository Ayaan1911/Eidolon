from fastapi import APIRouter, HTTPException, Request

from models.schemas import AdminLoginRequest, AdminLoginResponse
from routers.exposure import limiter
from services.admin_auth import issue_token, passphrase_matches

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/login", response_model=AdminLoginResponse)
@limiter.limit("5/minute")
async def admin_login(request: Request, body: AdminLoginRequest) -> AdminLoginResponse:
    # Deliberately generic: nothing about why a login failed (wrong passphrase,
    # ADMIN_KEY unset) is ever reported back.
    if not passphrase_matches(body.passphrase):
        raise HTTPException(status_code=401, detail="Unauthorized")
    token, expires_at = issue_token()
    return AdminLoginResponse(token=token, expires_at=expires_at)
