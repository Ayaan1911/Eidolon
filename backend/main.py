import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from routers.admin import router as admin_router
from routers.exposure import limiter, router as exposure_router
from routers.ready import router as ready_router
from routers.traps import router as traps_router
from database import SessionLocal
from services.client_ip import trusted_proxy_hops
from services.logging_setup import RequestIdMiddleware, configure_logging
from services.retention import delete_old_alerts, retention_days
from services.startup_checks import check_database, check_log_level, check_public_base_url, check_secrets

# Local dev: read backend/.env. Variables already set in the real environment (Render) win.
load_dotenv()

# Logging first, so everything after this (including a startup refusal) is logged the same way.
check_log_level()
configure_logging()

# Fail closed: weak or missing secrets stop the app from starting (see startup_checks.py).
check_secrets()
check_database()
check_public_base_url()

# Refuse to start on a bad TRUSTED_PROXY_HOPS instead of failing on every request later.
trusted_proxy_hops()

log = logging.getLogger("eidolon")

# A bad RETENTION_DAYS stops startup here instead of surfacing later.
retention_days()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Once per start, after migrations (the deploy command runs `alembic upgrade head` first).
    # A database problem here must not keep the API down, so it is reported and startup goes on.
    log.info("eidolon starting (commit %s)", os.environ.get("RENDER_GIT_COMMIT", "unknown")[:7])
    try:
        with SessionLocal() as db:
            delete_old_alerts(db)
    except Exception as e:
        log.warning("retention cleanup skipped: %s", type(e).__name__)  # the type only: messages can name hosts
    yield


app = FastAPI(title="Eidolon API", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Comma-separated deployed frontend origins, e.g. "https://eidolon.vercel.app" (no trailing slash needed).
allowed_origins = [o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    # any localhost port covers Vite's dev-port fallback
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

# Added last, so it is the outermost layer: every response (even a CORS one) carries X-Request-ID.
app.add_middleware(RequestIdMiddleware)

app.include_router(admin_router)
app.include_router(exposure_router)
app.include_router(ready_router)
app.include_router(traps_router)


@app.get("/health")
async def health() -> dict[str, str]:
    # Render sets RENDER_GIT_COMMIT on every deploy, so this answers "is the
    # latest fix actually live?" without opening the dashboard.
    return {"status": "ok", "commit": os.environ.get("RENDER_GIT_COMMIT", "unknown")[:7]}
