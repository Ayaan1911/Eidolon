import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from routers.exposure import limiter, router as exposure_router
from routers.traps import router as traps_router

app = FastAPI(title="Eidolon API")
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

app.include_router(exposure_router)
app.include_router(traps_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
