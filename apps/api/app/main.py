import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.db import engine
from app.core.errors import register_error_handlers
from app.core.logging import logger, setup_logging
import app.models  # Ensure all model tables are registered in Base.metadata
from app.models import Base
from app.routers.auth import router as auth_router
from app.routers.elders import router as elders_router
from app.routers.health import router as health_router
from app.routers.medicines import router as medicines_router
from app.routers.status import router as status_router
from app.routers.sos import router as sos_router
from app.routers.notifications import router as notifications_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("aira_api_starting", env=settings.APP_ENV)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    logger.info("aira_api_shutting_down")
    if settings.APP_ENV != "test":
        await engine.dispose()


app = FastAPI(
    title="AIRA Care API",
    version="0.1.0",
    description="Care that listens. Companionship that cares.",
    lifespan=lifespan,
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.WEB_ORIGIN, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Error handlers
register_error_handlers(app)

# Include Routers
app.include_router(health_router)
app.include_router(auth_router)
app.include_router(elders_router)
app.include_router(medicines_router)
app.include_router(status_router)
app.include_router(sos_router)
app.include_router(notifications_router)


@app.get("/api/v1/stream")
async def sse_stream() -> StreamingResponse:
    """Server-Sent Events stream for live SOS banners and notification badge counts."""
    async def event_generator() -> AsyncGenerator[str, None]:
        # Initial connection handshake
        yield "event: connected\ndata: {\"status\": \"connected\"}\n\n"
        while True:
            await asyncio.sleep(15)
            # Periodic keep-alive ping
            yield "event: ping\ndata: {\"timestamp\": \"keepalive\"}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
