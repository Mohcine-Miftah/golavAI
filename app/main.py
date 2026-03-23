"""
app/main.py — FastAPI application factory.
"""
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from app.core.logging import configure_logging, correlation_id_var, get_logger
from app.api.webhooks import twilio_inbound, twilio_status
from app.api.admin import bookings as admin_bookings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(
        log_level=settings.app_log_level,
        json_logs=(settings.app_env == "production"),
    )
    logger.info("golav_startup", env=settings.app_env)
    yield
    logger.info("golav_shutdown")


app = FastAPI(
    title="GOLAV Booking Agent",
    description="AI-powered WhatsApp booking agent for GOLAV car wash",
    version="0.1.0",
    lifespan=lifespan,
)

# ── Prometheus metrics ────────────────────────────────────────────────────────
Instrumentator().instrument(app).expose(app, endpoint="/metrics")


# ── Correlation ID middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    correlation_id_var.set(cid)
    response = await call_next(request)
    response.headers["X-Correlation-ID"] = cid
    return response


# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(twilio_inbound.router, prefix="/webhooks/twilio", tags=["webhooks"])
app.include_router(twilio_status.router, prefix="/webhooks/twilio", tags=["webhooks"])
app.include_router(admin_bookings.router, prefix="/admin", tags=["admin"])


# ── Health endpoints ──────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def ready():
    """Readiness check — verifies DB and Redis are reachable."""
    from app.db.session import engine
    from redis.asyncio import Redis

    db_ok = False
    redis_ok = False
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    try:
        redis = Redis.from_url(settings.redis_url)
        await redis.ping()
        await redis.aclose()
        redis_ok = True
    except Exception:
        pass

    if not db_ok or not redis_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "db": db_ok, "redis": redis_ok},
        )
    return {"status": "ready", "db": db_ok, "redis": redis_ok}
