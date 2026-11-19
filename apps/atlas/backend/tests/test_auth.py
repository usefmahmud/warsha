"""Auth lifecycle, profile, password and login throttling (Epic A)."""

from __future__ import annotations

from tests.conftest import PASSWORD, bearer


def test_bootstrap_register_creates_owner(client):
    data = client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "username": "youssef",
            "name": "يوسف",
            "password": PASSWORD,
            "role": "admin",  # ignored: the bootstrap account is always owner
        },
    ).json()
    assert data["user"]["role"] == "owner"
    assert data["token_type"] == "bearer"
    assert data["expires_in"] == 12 * 3600
    assert "password_hash" not in data["user"]


def test_second_self_registration_is_closed(client, owner):
    resp = client.post(
        "/api/auth/register",
        json={
            "email": "other@example.com",
            "username": "other",
            "name": "Other",
            "password": PASSWORD,
        },
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "REGISTRATION_CLOSED"


def test_login_success_and_me(client, owner):
    resp = client.post(
        "/api/auth/login", json={"email": "youssef@example.com", "password": PASSWORD}
    )
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    me = client.get("/api/auth/me", headers=bearer(token))
    assert me.status_code == 200
    assert me.json()["username"] == "youssef"
    assert me.json()["last_login_at"] is not None


def test_login_wrong_password_is_generic(client, owner):
    wrong = client.post(
        "/api/auth/login", json={"email": "youssef@example.com", "password": "nope-nope"}
    )
    unknown = client.post(
        "/api/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


def test_login_throttled_after_five_failures(client, owner):
    for _ in range(5):
        resp = client.post(
            "/api/auth/login", json={"email": "youssef@example.com", "password": "wrong-pass"}
        )
        assert resp.status_code == 401
    blocked = client.post(
        "/api/auth/login", json={"email": "youssef@example.com", "password": PASSWORD}
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "TOO_MANY_ATTEMPTS"
    assert "Retry-After" in blocked.headers


def test_disabled_account_cannot_login_and_tokens_die(client, owner_headers, member):
    member_id = member["user"]["id"]
    token = member["access_token"]
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 200

    assert (
        client.post(f"/api/users/{member_id}/deactivate", headers=owner_headers).status_code == 204
    )
    login = client.post("/api/auth/login", json={"email": "omar@example.com", "password": PASSWORD})
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "ACCOUNT_DISABLED"

    stale = client.get("/api/auth/me", headers=bearer(token))
    assert stale.status_code == 401
    assert stale.json()["error"]["code"] == "ACCOUNT_DISABLED"


def test_invalid_token(client):
    resp = client.get("/api/auth/me", headers=bearer("not-a-jwt"))
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "INVALID_TOKEN"


def test_profile_update_and_validation(client, owner_headers):
    ok = client.patch(
        "/api/auth/me", headers=owner_headers, json={"name": "يوسف محمود", "color": "#8B5CF6"}
    )
    assert ok.status_code == 200
    assert ok.json()["name"] == "يوسف محمود"
    assert ok.json()["color"] == "#8B5CF6"

    bad = client.patch("/api/auth/me", headers=owner_headers, json={"color": "red"})
    assert bad.status_code == 422
    assert bad.json()["error"]["details"][0]["field"] == "color"


def test_change_password(client, owner_headers):
    wrong = client.post(
        "/api/auth/password",
        headers=owner_headers,
        json={"current_password": "nope", "new_password": "Another-pass1"},
    )
    assert wrong.status_code == 400
    assert wrong.json()["error"]["code"] == "INVALID_PASSWORD"

    ok = client.post(
        "/api/auth/password",
        headers=owner_headers,
        json={"current_password": PASSWORD, "new_password": "Another-pass1"},
    )
    assert ok.status_code == 204
    assert (
        client.post(
            "/api/auth/login", json={"email": "youssef@example.com", "password": PASSWORD}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "youssef@example.com", "password": "Another-pass1"},
        ).status_code
        == 200
    )


def test_health_meta_and_openapi(client):
    health = client.get("/api/health").json()
    assert health["status"] == "ok" and health["db"] == "ok"
    assert client.get("/health").status_code == 200

    meta = client.get("/api/meta").json()
    assert [s["value"] for s in meta["statuses"]] == [
        "backlog",
        "todo",
        "in_progress",
        "review",
        "blocked",
        "done",
    ]
    assert len(meta["types"]) == 4 and len(meta["priorities"]) == 4

    spec = client.get("/api/openapi.json").json()
    assert "/api/agent/tickets" in spec["paths"]
    assert len(spec["paths"]) >= 45


def test_admin_creates_users_and_roles(client, owner_headers):
    created = client.post(
        "/api/users",
        headers=owner_headers,
        json={
            "email": "yassin@example.com",
            "username": "yassin",
            "name": "ياسين",
            "password": PASSWORD,
            "role": "member",
        },
    )
    assert created.status_code == 201

    dup = client.post(
        "/api/users",
        headers=owner_headers,
        json={
            "email": "yassin@example.com",
            "username": "yassin2",
            "name": "d",
            "password": PASSWORD,
        },
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "EMAIL_EXISTS"

    owner_id = client.get("/api/auth/me", headers=owner_headers).json()["id"]
    promoted = client.patch(
        f"/api/users/{owner_id}", headers=owner_headers, json={"role": "admin"}
    )
    assert promoted.status_code == 403  # cannot demote the last owner
    assert promoted.json()["error"]["code"] == "LAST_OWNER"
