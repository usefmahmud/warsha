"""Role matrix and information hiding (US-02, AC-02.x)."""

from __future__ import annotations

from tests.conftest import make_ticket


def test_member_cannot_create_project(client, member_headers):
    resp = client.post(
        "/api/projects", headers=member_headers, json={"key": "OPS", "name": "Ops"}
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_admin_can_create_project(client, admin_headers):
    resp = client.post(
        "/api/projects", headers=admin_headers, json={"key": "OPS", "name": "Operations"}
    )
    assert resp.status_code == 201
    assert resp.json()["my_role"] == "lead"


def test_non_member_gets_404_not_403(client, project, member_headers):
    for path in ("/api/projects/ATL", "/api/projects/ATL/board", "/api/projects/ATL/tickets"):
        resp = client.get(path, headers=member_headers)
        assert resp.status_code == 404, path
        assert resp.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_member_cannot_delete_ticket(client, project_with_member, member_headers, owner_headers):
    ticket = make_ticket(client, owner_headers, title="Protected")
    resp = client.delete(f"/api/tickets/{ticket['key']}", headers=member_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"
    assert client.get(f"/api/tickets/{ticket['key']}", headers=owner_headers).status_code == 200


def test_admin_cannot_modify_owner_account(client, owner, admin_headers):
    owner_id = owner["user"]["id"]
    resp = client.patch(
        f"/api/users/{owner_id}", headers=admin_headers, json={"role": "member"}
    )
    assert resp.status_code == 403


def test_member_manages_own_api_key_only(client, owner_headers, member, member_headers):
    own = client.post(
        f"/api/users/{member['user']['id']}/keys",
        headers=member_headers,
        json={"name": "cli"},
    )
    assert own.status_code == 201

    other_id = client.get("/api/auth/me", headers=owner_headers).json()["id"]
    forbidden = client.post(
        f"/api/users/{other_id}/keys", headers=member_headers, json={"name": "steal"}
    )
    assert forbidden.status_code == 403


def test_activity_is_read_only(client, project_with_member, owner_headers):
    ticket = make_ticket(client, owner_headers)
    activity = client.get(f"/api/tickets/{ticket['key']}/activity", headers=owner_headers).json()
    activity_id = activity["items"][0]["id"]

    assert (
        client.patch(f"/api/activity/{activity_id}", headers=owner_headers, json={}).status_code
        in (404, 405)
    )
    assert client.delete(f"/api/activity/{activity_id}", headers=owner_headers).status_code in (
        404,
        405,
    )
