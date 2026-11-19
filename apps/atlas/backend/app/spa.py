"""Serve the built SPA (frontend/dist) from the API process — one container, one port."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def mount_spa(app: FastAPI, dist: Path) -> bool:
    """Mount /assets + SPA fallback. Returns True when a build was found."""
    index = dist / "index.html"
    if not index.is_file():
        return False

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path.startswith("api") or full_path == "api":
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (dist / full_path).resolve() if full_path else None
        if candidate and candidate.is_file() and dist.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index)

    return True
