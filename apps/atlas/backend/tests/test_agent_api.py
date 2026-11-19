"""Agent API: keys, idempotency, permissions (Epic F)."""

from __future__ import annotations

from tests.conftest import make_ticket


def _issue_key(client, headers, name="agent") -> str:
    me = client.get("/api/auth/me", headers=headers).json()
    resp = client.post(
        f"/api/users/{me['id']}/keys", headers=headers, json={"name": name}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["key"].startswith("atl_")
    assert body["prefix"] == body["key"][:12]
    return body["key"]


def test_key_is_shown_once(client, owner_headers, owner):
    key = _issue_key(client, owner_headers, "hermes")
    keys = client.get(f"/api/users/{owner['user']['id']}/keys", headers=owner_headers).json()
    assert len(keys) == 1
    assert keys[0]["prefix"] == key[:12]
    assert "key" not in keys[0] and "key_hash" not in keys[0]
    assert key not in str(keys)


def test_agent_me_and_last_used(client, owner_headers, project):
    key = _issue_key(client, owner_headers)
    me = client.get("/api/agent/me", headers={"X-API-Key": key})
    assert me.status_code == 200
    assert me.json()["user"]["username"] == "youssef"
    assert {"key": "ATL", "name": "Atlas"} in me.json()["projects"]

    keys = client.get(
        "/api/users/" + client.get("/api/auth/me", headers=owner_headers).json()["id"] + "/keys",
        headers=owner_headers,
    ).json()
    assert keys[0]["last_used_at"] is not None


def test_agent_creates_ticket(client, owner_headers, project):
    key = _issue_key(client, owner_headers)
    resp = client.post(
        "/api/agent/tickets",
        headers={"X-API-Key": key},
        json={
            "project_key": "ATL",
            "title": "Agent ticket",
            "description_md": "opened by CLI",
            "type": "chore",
            "priority": "high",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["key"] == "ATL-1"
    assert body["reporter"]["username"] == "youssef"
    assert body["priority"] == "high"

    activity = client.get(f"/api/tickets/{body['key']}/activity", headers=owner_headers).json()
    assert activity["items"][0]["action"] == "created"


def test_client_ref_is_idempotent(client, owner_headers, project):
    key = _issue_key(client, owner_headers)
    payload = {"project_key": "ATL", "title": "run 42", "client_ref": "run-42-step-3"}
    first = client.post("/api/agent/tickets", headers={"X-API-Key": key}, json=payload)
    second = client.post("/api/agent/tickets", headers={"X-API-Key": key}, json=payload)
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]

    listed = client.get("/api/projects/ATL/tickets", headers=owner_headers).json()
    assert listed["total"] == 1


def test_missing_or_bad_key(client, project):
    assert client.post("/api/agent/tickets", json={"project_key": "ATL", "title": "x"}).status_code == 401
    bad = client.post(
        "/api/agent/tickets",
        headers={"X-API-Key": "atl_nope_nope"},
        json={"project_key": "ATL", "title": "x"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["code"] == "INVALID_API_KEY"


def test_jwt_is_not_accepted_on_agent_routes(client, owner_headers, project):
    resp = client.post(
        "/api/agent/tickets", headers=owner_headers, json={"project_key": "ATL", "title": "x"}
    )
    assert resp.status_code == 401


def test_revoked_key_stops_working(client, owner_headers, owner):
    key = _issue_key(client, owner_headers)
    key_id = client.get(f"/api/users/{owner['user']['id']}/keys", headers=owner_headers).json()[0]["id"]
    assert client.delete(f"/api/keys/{key_id}", headers=owner_headers).status_code == 204
    resp = client.post(
        "/api/agent/tickets",
        headers={"X-API-Key": key},
        json={"project_key": "ATL", "title": "after revoke"},
    )
    assert resp.status_code == 401


def test_agent_outside_project_gets_403(client, owner_headers, project, member, member_headers):
    key = _issue_key(client, member_headers, "omar-bot")
    resp = client.post(
        "/api/agent/tickets",
        headers={"X-API-Key": key},
        json={"project_key": "ATL", "title": "sneaky"},
    )
    assert resp.status_code == 404  # project hidden from non-members (AC-02.4)


def test_agent_updates_and_comments(client, owner_headers, project_with_member, member_headers):
    key = _issue_key(client, member_headers)
    created = client.post(
        "/api/agent/tickets",
        headers={"X-API-Key": key},
        json={"project_key": "ATL", "title": "Agent flow", "status": "todo"},
    ).json()

    moved = client.post(
        f"/api/agent/tickets/{created['key']}/transition",
        headers={"X-API-Key": key},
        json={"to": "in_progress"},
    )
    assert moved.status_code == 200
    assert moved.json()["ticket"]["status"] == "in_progress"

    patched = client.patch(
        f"/api/agent/tickets/{created['key']}",
        headers={"X-API-Key": key},
        json={"priority": "urgent", "estimate_points": 5},
    )
    assert patched.status_code == 200
    assert patched.json()["priority"] == "urgent"

    comment = client.post(
        f"/api/agent/tickets/{created['key']}/comments",
        headers={"X-API-Key": key},
        json={"body_md": "progress @youssef"},
    )
    assert comment.status_code == 201
    assert [u["username"] for u in comment.json()["mentions"]] == ["youssef"]


def test_agent_my_tickets(client, owner_headers, project_with_member, member_headers, member):
    key = _issue_key(client, member_headers)
    client.post(
        "/api/agent/tickets",
        headers={"X-API-Key": key},
        json={
            "project_key": "ATL",
            "title": "assigned to me",
            "assignee_username": member["user"]["username"],
        },
    )
    listed = client.get("/api/agent/my-tickets", headers={"X-API-Key": key})
    assert listed.status_code == 200
    assert [t["title"] for t in listed.json()] == ["assigned to me"]


def test_agent_reuses_same_service_as_ui(client, owner_headers, project, labels):
    """AC-22.1: identical rules — unknown label fails the same way as the UI path."""
    key = _issue_key(client, owner_headers)
    resp = client.post(
        "/api/agent/tickets",
        headers={"X-API-Key": key},
        json={"project_key": "ATL", "title": "x", "labels": ["ghost"]},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "LABEL_NOT_FOUND"


def test_agent_cannot_delete_ticket(client, owner_headers, project_with_member, member_headers):
    ticket = make_ticket(client, owner_headers, title="keep me")
    key = _issue_key(client, member_headers)
    resp = client.delete(f"/api/tickets/{ticket['key']}", headers={"X-API-Key": key})
    assert resp.status_code == 401  # no DELETE route for agents / keys not accepted on UI routes
