"""Pytest fixtures: isolated SQLite DB per test + helpers for the PRD contract."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="atlas-tests-"))

# Settings are read at import time, so configure the environment first.
os.environ["ATLAS_ENV"] = "test"
os.environ["ATLAS_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ATLAS_DATABASE_URL"] = f"sqlite:///{_TMP / 'atlas-test.db'}"
os.environ["ATLAS_ALLOW_REGISTRATION"] = "true"
os.environ["ATLAS_ALLOW_PRIVATE_WEBHOOKS"] = "false"
os.environ["ATLAS_RATE_LIMIT_PER_MINUTE"] = "100000"
os.environ["ATLAS_LOGIN_ATTEMPTS_PER_MINUTE"] = "5"

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app, request_limiter

PASSWORD = "S3cret-pass"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    request_limiter.clear()
    import app.routers.auth as auth_module

    auth_module.login_limiter.clear()
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register(client: TestClient, username: str = "youssef", **extra) -> dict:
    payload = {
        "email": extra.pop("email", f"{username}@example.com"),
        "name": extra.pop("name", username.title()),
        "username": username,
        "password": extra.pop("password", PASSWORD),
        **extra,
    }
    resp = client.post("/api/auth/register", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def owner(client) -> dict:
    return register(client, "youssef", name="يوسف")


@pytest.fixture()
def owner_headers(owner) -> dict:
    return bearer(owner["access_token"])


@pytest.fixture()
def admin_user(client, owner_headers) -> dict:
    resp = client.post(
        "/api/users",
        headers=owner_headers,
        json={
            "email": "maryam@example.com",
            "username": "maryam",
            "name": "مريم",
            "password": PASSWORD,
            "role": "admin",
        },
    )
    assert resp.status_code == 201, resp.text
    login = client.post(
        "/api/auth/login", json={"email": "maryam@example.com", "password": PASSWORD}
    )
    assert login.status_code == 200
    return login.json()


@pytest.fixture()
def admin_headers(admin_user) -> dict:
    return bearer(admin_user["access_token"])


@pytest.fixture()
def member(client, owner_headers) -> dict:
    resp = client.post(
        "/api/users",
        headers=owner_headers,
        json={
            "email": "omar@example.com",
            "username": "omar",
            "name": "عمر",
            "password": PASSWORD,
            "role": "member",
        },
    )
    assert resp.status_code == 201, resp.text
    login = client.post("/api/auth/login", json={"email": "omar@example.com", "password": PASSWORD})
    return login.json()


@pytest.fixture()
def member_headers(member) -> dict:
    return bearer(member["access_token"])


@pytest.fixture()
def project(client, owner_headers) -> dict:
    resp = client.post(
        "/api/projects", headers=owner_headers, json={"key": "ATL", "name": "Atlas"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture()
def project_with_member(client, owner_headers, project, member) -> dict:
    resp = client.post(
        f"/api/projects/{project['key']}/members",
        headers=owner_headers,
        json={"user_id": member["user"]["id"], "role_in_project": "member"},
    )
    assert resp.status_code == 204, resp.text
    return project


@pytest.fixture()
def labels(client, owner_headers, project) -> dict:
    out = {}
    for name, color in (("backend", "#2563EB"), ("frontend", "#8B5CF6")):
        resp = client.post(
            f"/api/projects/{project['key']}/labels",
            headers=owner_headers,
            json={"name": name, "color": color},
        )
        assert resp.status_code == 201, resp.text
        out[name] = resp.json()
    return out


def make_ticket(client, headers, project_key: str = "ATL", **overrides):
    payload = {"title": "Ticket", **overrides}
    resp = client.post(f"/api/projects/{project_key}/tickets", headers=headers, json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()
