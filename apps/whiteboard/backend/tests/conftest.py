"""Pytest fixtures: isolated SQLite DB per test session + a TestClient."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="whiteboard-tests-"))

# Settings are read at import time, so configure the environment first.
os.environ["WB_ENV"] = "test"
os.environ["WB_DATABASE_URL"] = f"sqlite:///{_TMP / 'whiteboard-test.db'}"
os.environ["WB_STATIC_DIR"] = str(_TMP / "no-dist")

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app

SCENE = {"version": "6.0.0", "objects": [], "background": "#0b1020"}


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def board(client):
    """A board created through the API, as the frontend would."""
    r = client.post("/api/boards", json={"name": "بورد اختبار", "color": "#22d3ee"})
    assert r.status_code == 201, r.text
    return r.json()


def scene_with(*objects) -> dict:
    return {"version": "6.0.0", "objects": list(objects), "background": "#0b1020"}


def rect(**kw) -> dict:
    base = {
        "type": "rect",
        "left": 10,
        "top": 20,
        "width": 120,
        "height": 80,
        "fill": "#6366f1",
        "strokeWidth": 2,
        "scaleX": 1,
        "scaleY": 1,
        "angle": 0,
    }
    base.update(kw)
    return base
