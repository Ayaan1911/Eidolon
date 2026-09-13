from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from PIL import UnidentifiedImageError
from slowapi import Limiter
from slowapi.util import get_remote_address

from models.schemas import (
    EmailCheckRequest,
    EmailCheckResponse,
    PasswordCheckRequest,
    PasswordCheckResponse,
    PhotoMetadataResponse,
    RepoScanRequest,
    RepoScanResponse,
)
from services.breach_check import BreachCheckError, check_email_exposure
from services.github_scanner import GitHubScanError, scan_user_repos
from services.password_strength import check_password_strength
from services.photo_metadata import extract_photo_metadata

router = APIRouter(prefix="/api/exposure", tags=["exposure"])
limiter = Limiter(key_func=get_remote_address)

MAX_PHOTO_BYTES = 10 * 1024 * 1024


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


@router.post("/photo", response_model=PhotoMetadataResponse)
@limiter.limit("10/minute")
async def exposure_photo(request: Request, file: UploadFile = File(...)) -> PhotoMetadataResponse:
    image_bytes = await file.read()
    if len(image_bytes) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10MB limit")
    try:
        return extract_photo_metadata(image_bytes)
    except UnidentifiedImageError as e:
        raise HTTPException(status_code=400, detail="Could not read this file as an image") from e


# ponytail: lower limit than the other endpoints — each scan burns ~10+ GitHub API
# calls against the unauthenticated 60/hour quota, so 10/minute here would exhaust it fast
@router.post("/repos", response_model=RepoScanResponse)
@limiter.limit("5/minute")
async def exposure_repos(request: Request, body: RepoScanRequest) -> RepoScanResponse:
    try:
        return await scan_user_repos(body.username)
    except GitHubScanError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
