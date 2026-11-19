"""pytest fixtures — every test runs against a throwaway SQLite file."""

from __future__ import annotations

import os
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_TMP = Path(tempfile.mkdtemp(prefix="todo-test-"))
os.environ["TODO_DATABASE_URL"] = f"sqlite:///{_TMP / 'test.db'}"
os.environ["TODO_ENV"] = "test"
os.environ["TODO_STATIC_DIR"] = str(_TMP / "no-dist")

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app as fastapi_app


@pytest.fixture()
def client() -> TestClient:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(fastapi_app) as c:
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def make_todo(client):
    """Factory: make_todo({"title": "x", ...}) -> created JSON."""

    def _make(**overrides):
        payload = {"title": f"مهمة {uuid.uuid4().hex[:6]}"}
        payload.update(overrides)
        r = client.post("/api/todos", json=payload)
        assert r.status_code == 201, r.text
        return r.json()

    return _make
