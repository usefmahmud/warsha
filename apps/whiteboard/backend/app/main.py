"""FastAPI application factory — Whiteboard API + static SPA host."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .config import settings
from .database import SessionLocal, init_db
from .routers import boards
from .spa import mount_spa

VERSION = "1.0.0"
log = logging.getLogger("whiteboard")
STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    log.info("whiteboard %s started (env=%s)", VERSION, settings.env)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version=VERSION,
        description="Self-hosted whiteboard: boards CRUD, autosave, read-only share links.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(boards.router)

    @app.get("/api/health", tags=["meta"])
    def health():
        started = time.time()
        detail = {"status": "ok", "version": VERSION}
        try:
            with SessionLocal() as db:
                db.execute(text("SELECT 1"))
        except Exception:  # pragma: no cover - only when the DB is broken
            detail["status"] = "degraded"
            detail["db"] = "error"
        detail["ms"] = round((time.time() - started) * 1000, 2)
        detail["uptime_s"] = round(time.time() - STARTED_AT, 1)
        return detail

    dist = Path(settings.static_dir or (Path(__file__).resolve().parents[2] / "frontend" / "dist"))
    if mount_spa(app, dist):
        log.info("serving SPA from %s", dist)
    else:
        log.info("no SPA build at %s (API only)", dist)

    return app


app = create_app()
