"""Readiness (/ready) and the root page (/). /health, which only says the process is alive, lives in main.py."""

import logging
import os
import time
from functools import lru_cache
from pathlib import Path

import anyio
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy import text

from database import session_scope
from routers.exposure import limiter

router = APIRouter()
log = logging.getLogger("eidolon.ready")

DB_CHECK_TIMEOUT_SECONDS = 2
# Per client IP. Render's checker calls about every 5 seconds (12 a minute); a 429 here would read as "not ready".
READY_LIMIT = "60/minute"
# The answer (ready or not) is reused for this long, so probes and visitors cause about 2 database checks a minute.
READY_CACHE_SECONDS = 30
_cache: tuple[float, str | None] | None = None  # (expiry on time.monotonic(), reason or None)
_ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


@lru_cache
def head_revision() -> str | None:
    """The newest migration in the repo (read from the migration files; the code never changes while running)."""
    return ScriptDirectory.from_config(Config(str(_ALEMBIC_INI))).get_current_head()


def _database_revision() -> str | None:
    """SELECT 1, then the revision the database says it is at (None if it was never migrated)."""
    with session_scope() as db:
        db.execute(text("SELECT 1"))
        return MigrationContext.configure(db.connection()).get_current_revision()


async def not_ready_reason() -> str | None:
    """None when ready, else a short generic reason (cached for READY_CACHE_SECONDS)."""
    global _cache
    now = time.monotonic()
    if _cache and now < _cache[0]:
        return _cache[1]
    reason = await _check()
    _cache = (now + READY_CACHE_SECONDS, reason)
    return reason


async def _check() -> str | None:
    """The real check. Only the exception class name is ever logged:
    driver errors can contain the host, the user or the URL."""
    try:
        with anyio.fail_after(DB_CHECK_TIMEOUT_SECONDS):
            # abandon_on_cancel: on timeout we answer at once instead of waiting for a stuck connection.
            revision = await anyio.to_thread.run_sync(_database_revision, abandon_on_cancel=True)
    except Exception as e:  # a timeout, a refused connection, a bad password: all "unreachable"
        log.warning("not ready: database check failed (%s)", type(e).__name__)
        return "database_unreachable"
    if revision != head_revision():
        log.warning("not ready: database migrations are not at the repo's head")
        return "migrations_out_of_date"
    return None


@router.get("/ready")
@limiter.limit(READY_LIMIT)
async def ready(request: Request) -> JSONResponse:
    reason = await not_ready_reason()
    if reason:
        return JSONResponse({"status": "not_ready", "reason": reason}, status_code=503)
    return JSONResponse({"status": "ready", "commit": os.environ.get("RENDER_GIT_COMMIT", "unknown")[:7]})


# Render (and browsers) request "/"; without this every probe is a 404 in the logs.
@router.api_route("/", methods=["GET", "HEAD"], include_in_schema=False)
async def root() -> PlainTextResponse:
    return PlainTextResponse("Eidolon API")
