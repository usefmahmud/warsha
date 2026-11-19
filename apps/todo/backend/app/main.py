"""FastAPI application factory for the TODO app."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from datetime import UTC
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .database import init_db
from .errors import install_error_handlers, new_request_id
from .routers import todos
from .schemas import HealthOut
from .spa import mount_spa

VERSION = "1.0.0"
log = logging.getLogger("todo")
STARTED_AT = time.time()

DEFAULT_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    log.info("todo %s started (env=%s)", VERSION, settings.env)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=VERSION,
        description="TODO — simple, self-hosted task list. Dark RTL UI served from the same port.",
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
        expose_headers=["X-Request-Id"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("X-Request-Id") or new_request_id()
        request.state.request_id = rid
        try:
            response = await call_next(request)
        except Exception:  # pragma: no cover - defensive
            log.exception("unhandled error on %s %s", request.method, request.url.path)
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "unexpected server error",
                        "request_id": rid,
                    }
                },
            )
        response.headers["X-Request-Id"] = rid
        return response

    install_error_handlers(app)
    app.include_router(todos.router, prefix=settings.api_prefix)

    # `/health` (root) is an alias for container healthchecks — deploy tooling
    # probes it before the SPA fallback is mounted.
    @app.get("/api/health", response_model=HealthOut, tags=["meta"])
    @app.get("/health", response_model=HealthOut, tags=["meta"], include_in_schema=False)
    def health() -> HealthOut:
        from datetime import datetime

        return HealthOut(
            status="ok",
            app=settings.app_name,
            version=VERSION,
            db="sqlite" if settings.database_url.startswith("sqlite") else "other",
            time=datetime.now(UTC),
        )

    @app.get("/api/meta", tags=["meta"])
    def meta() -> dict:
        from .models import PRIORITY_LABELS, TodoPriority

        return {
            "app": settings.app_name,
            "version": VERSION,
            "uptime_s": round(time.time() - STARTED_AT, 1),
            "priorities": [
                {"value": p.value, "label": PRIORITY_LABELS[p]}
                for p in (TodoPriority.high, TodoPriority.normal, TodoPriority.low)
            ],
        }

    dist = Path(settings.static_dir) if settings.static_dir else DEFAULT_DIST
    if not mount_spa(app, dist):
        log.warning("no SPA build at %s — API only", dist)

    return app


app = create_app()
