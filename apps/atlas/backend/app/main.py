"""FastAPI application factory."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import settings
from .database import SessionLocal, init_db
from .errors import envelope, install_error_handlers, new_request_id
from .models import STATUS_LABELS, STATUS_ORDER, TicketPriority, TicketType
from .ratelimit import SlidingWindow
from .routers import (
    agent,
    auth,
    comments,
    labels,
    notifications,
    projects,
    search,
    tickets,
    users,
    webhooks,
)
from .schemas import HealthOut, MetaOut, OptionOut
from .spa import mount_spa

VERSION = "1.0.0"
log = logging.getLogger("atlas")
STARTED_AT = time.time()
request_limiter = SlidingWindow(settings.rate_limit_per_minute, 60.0)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    log.info("atlas %s started (env=%s)", VERSION, settings.env)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=VERSION,
        description=(
            "Self-hosted project & ticket management for the team.\n\n"
            "- **Humans**: `POST /api/auth/login` → `Authorization: Bearer <token>`\n"
            "- **Agents**: `X-API-Key: atl_<prefix>_<secret>` on `/api/agent/*`\n"
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id", "Retry-After"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or new_request_id()
        request.state.request_id = rid
        if request.url.path not in ("/api/health", "/health"):
            key = request.headers.get("Authorization") or request.client.host if request.client else "anon"
            if not request_limiter.hit(key):
                retry = request_limiter.retry_after(key)
                response = JSONResponse(
                    status_code=429,
                    content=envelope(
                        "TOO_MANY_ATTEMPTS", "rate limit exceeded", None, rid
                    ),
                    headers={"Retry-After": str(retry)},
                )
                response.headers["X-Request-Id"] = rid
                return response
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        return response

    install_error_handlers(app)
    for module in (
        auth,
        users,
        projects,
        tickets,
        comments,
        labels,
        notifications,
        search,
        agent,
        webhooks,
    ):
        app.include_router(module.router, prefix=settings.api_prefix)

    @app.get(f"{settings.api_prefix}/health", response_model=HealthOut, tags=["meta"])
    @app.get("/health", response_model=HealthOut, tags=["meta"], include_in_schema=False)
    def health() -> HealthOut:
        db_status = "ok"
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
        except Exception as exc:  # noqa: BLE001
            db_status = f"error: {exc}"
        return HealthOut(
            status="ok", db=db_status, version=VERSION, uptime_s=round(time.time() - STARTED_AT, 1)
        )

    @app.get(f"{settings.api_prefix}/meta", response_model=MetaOut, tags=["meta"])
    def meta() -> MetaOut:
        return MetaOut(
            statuses=[OptionOut(value=s.value, label=STATUS_LABELS[s]) for s in STATUS_ORDER],
            types=[OptionOut(value=t.value, label=t.value.title()) for t in TicketType],
            priorities=[
                OptionOut(value=p.value, label=p.value.title()) for p in TicketPriority
            ],
            version=VERSION,
        )

    @app.get("/", include_in_schema=False)
    def root():
        spa_index = Path(settings.static_dir) / "index.html" if settings.static_dir else None
        if spa_index and spa_index.is_file():
            from fastapi.responses import FileResponse

            return FileResponse(spa_index)
        return {
            "app": settings.app_name,
            "version": VERSION,
            "docs": "/docs",
            "openapi": "/api/openapi.json",
            "health": "/api/health",
        }

    if settings.static_dir:
        mount_spa(app, Path(settings.static_dir))

    return app


app = create_app()
