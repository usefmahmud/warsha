"""Projects: creation rules, archive, members, board (Epic B)."""

from __future__ import annotations

from tests.conftest import make_ticket


def test_project_key_rules(client, owner_headers):
    for bad_key in ("atl", "atlas!", "ATLASBX", "A", "1AT"):
        resp = client.post(
            "/api/projects", headers=owner_headers, json={"key": bad_key, "name": "x"}
        )
        assert resp.status_code == 422, bad_key

    ok = client.post("/api/projects", headers=owner_headers, json={"key": "ATL2", "name": "x"})
    assert ok.status_code == 201


def test_duplicate_key_conflict(client, project, owner_headers):
    resp = client.post("/api/projects", headers=owner_headers, json={"key": "ATL", "name": "dup"})
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "PROJECT_KEY_EXISTS"


def test_new_project_has_six_empty_columns(client, owner_headers, project):
    board = client.get("/api/projects/ATL/board", headers=owner_headers).json()
    assert [c["status"] for c in board["columns"]] == [
        "backlog",
        "todo",
        "in_progress",
        "review",
        "blocked",
        "done",
    ]
    assert all(c["count"] == 0 and c["items"] == [] for c in board["columns"])
    assert board["project"]["ticket_count"] == 0


def test_archive_hides_project_and_blocks_board(client, owner_headers, project):
    assert client.post("/api/projects/ATL/archive", headers=owner_headers).status_code == 204

    listed = client.get("/api/projects", headers=owner_headers).json()
    assert all(p["key"] != "ATL" for p in listed["items"])

    with_archived = client.get(
        "/api/projects", headers=owner_headers, params={"include_archived": "true"}
    ).json()
    assert any(p["key"] == "ATL" for p in with_archived["items"])

    board = client.get("/api/projects/ATL/board", headers=owner_headers)
    assert board.status_code == 404
    assert board.json()["error"]["code"] == "PROJECT_ARCHIVED"

    assert client.post("/api/projects/ATL/unarchive", headers=owner_headers).status_code == 204
    assert client.get("/api/projects/ATL/board", headers=owner_headers).status_code == 200


def test_members_add_and_conflict(client, owner_headers, project, member):
    url = "/api/projects/ATL/members"
    assert (
        client.post(f"{url}", headers=owner_headers, json={"user_id": member["user"]["id"]}).status_code
        == 204
    )
    dup = client.post(f"{url}", headers=owner_headers, json={"user_id": member["user"]["id"]})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "MEMBER_EXISTS"

    members = client.get(url, headers=owner_headers).json()
    assert {m["user"]["username"] for m in members} == {"youssef", "omar"}


def test_removing_member_unassigns_tickets(
    client, owner_headers, project, member, member_headers
):
    client.post("/api/projects/ATL/members", headers=owner_headers, json={"user_id": member["user"]["id"]})
    ticket = make_ticket(
        client, owner_headers, title="Assigned", assignee_username=member["user"]["username"]
    )
    assert ticket["assignee"]["username"] == "omar"

    resp = client.delete(
        f"/api/projects/ATL/members/{member['user']['id']}", headers=owner_headers
    )
    assert resp.status_code == 204

    after = client.get(f"/api/tickets/{ticket['key']}", headers=owner_headers).json()
    assert after["assignee"] is None

    activity = client.get(f"/api/tickets/{ticket['key']}/activity", headers=owner_headers).json()
    assert any(row["action"] == "assignee_removed_by_membership" for row in activity["items"])


def test_only_lead_manages_members(client, project_with_member, member_headers, owner, member):
    resp = client.post(
        "/api/projects/ATL/members",
        headers=member_headers,
        json={"user_id": owner["user"]["id"]},
    )
    assert resp.status_code == 403

    # member can still read the member list
    assert client.get("/api/projects/ATL/members", headers=member_headers).status_code == 200


def test_project_detail_counts(client, owner_headers, project, labels):
    make_ticket(client, owner_headers, title="One", status="todo", labels=["backend"])
    make_ticket(client, owner_headers, title="Two")
    detail = client.get("/api/projects/ATL", headers=owner_headers).json()
    assert detail["ticket_count"] == 2
    assert detail["open_count"] == 2
    assert detail["members_count"] == 1
    assert {lb["name"] for lb in detail["labels"]} == {"backend", "frontend"}


def test_label_crud_and_conflicts(client, owner_headers, project, labels):
    dup = client.post(
        "/api/projects/ATL/labels", headers=owner_headers, json={"name": "BACKEND"}
    )
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "LABEL_EXISTS"

    renamed = client.patch(
        f"/api/labels/{labels['frontend']['id']}", headers=owner_headers, json={"name": "ui"}
    )
    assert renamed.status_code == 200 and renamed.json()["name"] == "ui"

    assert client.delete(f"/api/labels/{labels['ui']['id'] if 'ui' in labels else renamed.json()['id']}", headers=owner_headers).status_code == 204
