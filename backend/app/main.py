import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import engine
from app.core.opensearch import ensure_index_exists
from app.routers import admin, bidding, chat, financing, pricing, professionals, search, viewing

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("startup", env=settings.app_env)
    try:
        await ensure_index_exists()
        logger.info("opensearch_index_ready", index=settings.opensearch_index)
    except Exception as e:
        logger.warning("opensearch_index_init_failed", error=str(e))
    yield
    await engine.dispose()
    logger.info("shutdown")


app = FastAPI(
    title="Property Sahi Signal API",
    description="Your Sahi Signal Property Assistant — 6-stage Dublin property buying assistant",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next: any) -> Response:
    t0 = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = round((time.perf_counter() - t0) * 1000)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


PREFIX = "/api/v1"

app.include_router(search.router, prefix=PREFIX)
app.include_router(viewing.router, prefix=PREFIX)
app.include_router(bidding.router, prefix=PREFIX)
app.include_router(pricing.router, prefix=PREFIX)
app.include_router(professionals.router, prefix=PREFIX)
app.include_router(financing.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)
app.include_router(chat.router, prefix=PREFIX)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.app_env, "version": "0.1.0"}
