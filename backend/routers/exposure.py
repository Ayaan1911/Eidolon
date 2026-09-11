from fastapi import APIRouter, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.schemas import (
    EmailCheckRequest,
    EmailCheckResponse,
    PasswordCheckRequest,
    PasswordCheckResponse,
)
from services.breach_check import BreachCheckError, check_email_exposure
from services.password_strength import check_password_strength

router = APIRouter(prefix="/api/exposure", tags=["exposure"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/email", response_model=EmailCheckResponse)
@limiter.limit("10/minute")
async def exposure_email(request: Request, body: EmailCheckRequest) -> EmailCheckResponse:
    try:
        return await check_email_exposure(body.email)
    except BreachCheckError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/password", response_model=PasswordCheckResponse)
@limiter.limit("10/minute")
async def exposure_password(request: Request, body: PasswordCheckRequest) -> PasswordCheckResponse:
    return check_password_strength(body.password)
