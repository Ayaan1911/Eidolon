from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from PIL import UnidentifiedImageError
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from database import Trap, get_db
from models.schemas import (
    EmailCheckRequest,
    EmailCheckResponse,
    PasswordCheckRequest,
    PasswordCheckResponse,
    PhotoMetadataResponse,
    RepoScanRequest,
    RepoScanResponse,
    TrapStatus,
)
from services.admin_auth import is_admin_request
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
async def exposure_repos(
    request: Request, body: RepoScanRequest, db: Session = Depends(get_db)
) -> RepoScanResponse:
    try:
        result = RepoScanResponse(**await scan_user_repos(body.username))
    except GitHubScanError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    # This endpoint scans any GitHub username a visitor types in, not just the
    # site owner's own - so trap status (and its URL) is attached only for an
    # admin caller, never on a public scan of someone else's repos.
    if is_admin_request(request):
        finding_ids = [f.id for r in result.results for f in r.findings]
        if finding_ids:
            traps_by_finding = {
                t.finding_id: t
                for t in db.query(Trap).filter(Trap.finding_id.in_(finding_ids)).all()
            }
            for r in result.results:
                for f in r.findings:
                    trap = traps_by_finding.get(f.id)
                    if trap:
                        f.trap = TrapStatus(
                            trap_url=f"{request.base_url}trap/{trap.id}", hit_count=trap.trigger_count
                        )
    return result
