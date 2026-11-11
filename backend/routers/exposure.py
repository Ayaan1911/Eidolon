from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from slowapi import Limiter

from database import Trap, session_scope
from models.schemas import (
    EmailCheckRequest,
    EmailCheckResponse,
    PhotoMetadataResponse,
    RepoScanRequest,
    RepoScanResponse,
    TrapStatus,
)
from services.admin_auth import is_admin_request
from services.client_ip import get_client_ip
from services.breach_check import BreachCheckError, check_email_exposure
from services.github_scanner import GitHubScanError, scan_user_repos
from services.public_url import public_base_url
from services.photo_metadata import extract_photo_metadata

router = APIRouter(prefix="/api/exposure", tags=["exposure"])
limiter = Limiter(key_func=get_client_ip)

MAX_PHOTO_BYTES = 10 * 1024 * 1024


@router.post("/email", response_model=EmailCheckResponse)
@limiter.limit("10/minute")
async def exposure_email(request: Request, body: EmailCheckRequest) -> EmailCheckResponse:
    try:
        return await check_email_exposure(body.email)
    except BreachCheckError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.post("/photo", response_model=PhotoMetadataResponse)
@limiter.limit("10/minute")
async def exposure_photo(request: Request, file: UploadFile = File(...)) -> PhotoMetadataResponse:
    # Read one byte past the limit: enough to know it is too big, never the whole oversized file.
    image_bytes = await file.read(MAX_PHOTO_BYTES + 1)
    if len(image_bytes) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Image exceeds 10MB limit")
    try:
        # Pillow is CPU-bound: a worker thread keeps the event loop free for other requests.
        return await run_in_threadpool(extract_photo_metadata, image_bytes)
    except Exception as e:  # untrusted file: any parse failure (truncated, bomb, bad EXIF) is a plain 400
        raise HTTPException(status_code=400, detail="Could not read this file as an image") from e


# ponytail: lower limit than the other endpoints — each scan burns ~10+ GitHub API
# calls against the unauthenticated 60/hour quota, so 10/minute here would exhaust it fast
@router.post("/repos", response_model=RepoScanResponse)
@limiter.limit("5/minute")
async def exposure_repos(request: Request, body: RepoScanRequest) -> RepoScanResponse:
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
            hits = await run_in_threadpool(_trap_hits_by_finding, finding_ids)
            base = public_base_url(request)
            for r in result.results:
                for f in r.findings:
                    if f.id in hits:
                        trap_id, count = hits[f.id]
                        f.trap = TrapStatus(trap_url=f"{base}/trap/{trap_id}", hit_count=count)
    return result


def _trap_hits_by_finding(finding_ids: list[str]) -> dict[str, tuple[str, int]]:
    """finding id -> (trap id, hit count). Runs in a worker thread with its own session."""
    with session_scope() as db:
        traps = db.query(Trap).filter(Trap.finding_id.in_(finding_ids)).all()
        return {t.finding_id: (t.id, t.trigger_count) for t in traps}
