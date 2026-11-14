import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.core.db import engine, Base
from app.core.errors import register_error_handlers
from app.core.logging import logger, setup_logging
from app.routers.auth import router as auth_router
from app.routers.health import router as health_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("aira_api_starting", env=settings.APP_ENV)
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
