from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from routers.exposure import limiter, router as exposure_router

app = FastAPI(title="Eidolon API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    # ponytail: any localhost port covers Vite's dev-port fallback; pin to a real origin for prod
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exposure_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
