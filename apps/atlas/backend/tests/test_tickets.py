"""Tickets: numbering (incl. concurrency), fields, transitions, subtasks, delete."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from tests.conftest import make_ticket

OPEN_STATES = ["todo", "in_progress", "review"]


def test_first_ticket_numbering(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers, title="First")
    assert ticket["key"] == "ATL-1"
    assert ticket["number"] == 1
    assert ticket["version"] == 1
    assert ticket["status"] == "backlog"
    detail = client.get("/api/projects/ATL", headers=owner_headers).json()
    assert detail["key"] == "ATL"
    db_ticket = client.get(f"/api/tickets/{ticket['id']}", headers=owner_headers).json()
    assert db_ticket["key"] == "ATL-1"


def test_numbering_is_per_project(client, owner_headers, project):
    for i in range(1, 4):
        ticket = make_ticket(client, owner_headers, title=f"ATL {i}")
        assert ticket["key"] == f"ATL-{i}"
    other = client.post("/api/projects", headers=owner_headers, json={"key": "OPS", "name": "Ops"})
    assert other.status_code == 201
    ops_ticket = make_ticket(client, owner_headers, project_key="OPS", title="first ops")
    assert ops_ticket["key"] == "OPS-1"


def test_concurrent_creation_has_no_duplicates(client, owner_headers, project):
    """AC-08.3: 20 parallel creates → numbers 1..20, no gaps, no duplicates."""

    def create(i: int) -> str:
        resp = client.post(
            "/api/projects/ATL/tickets",
            headers=owner_headers,
            json={"title": f"parallel {i}"},
        )
        assert resp.status_code == 201, resp.text
        return resp.json()["key"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        keys = list(pool.map(create, range(20)))

    numbers = sorted(int(k.split("-")[1]) for k in keys)
    assert numbers == list(range(1, 21))
    assert len(set(keys)) == 20


def test_all_fields_and_labels(client, owner_headers, project, labels):
    ticket = make_ticket(
        client,
        owner_headers,
        title="Fix RTL",
        description_md="bug on **board**",
        type="bug",
        priority="urgent",
        labels=["backend", "frontend"],
        due_date="2026-11-20",
        estimate_points=5,
    )
    assert ticket["type"] == "bug"
    assert ticket["priority"] == "urgent"
    assert {lb["name"] for lb in ticket["labels"]} == {"backend", "frontend"}
    assert ticket["estimate_points"] == 5
    assert ticket["due_date"] == "2026-11-20"
    assert ticket["reporter"]["username"] == "youssef"
    assert ticket["description_md"].startswith("bug on")


def test_invalid_fields(client, owner_headers, project, member):
    too_long = client.post(
        "/api/projects/ATL/tickets", headers=owner_headers, json={"title": "x" * 201}
    )
    assert too_long.status_code == 422

    bad_type = client.post(
        "/api/projects/ATL/tickets", headers=owner_headers, json={"title": "x", "type": "epic"}
    )
    assert bad_type.status_code == 422

    outsider = client.post(
        "/api/projects/ATL/tickets",
        headers=owner_headers,
        json={"title": "x", "assignee_id": member["user"]["id"]},
    )
    assert outsider.status_code == 422
    assert outsider.json()["error"]["code"] == "ASSIGNEE_NOT_MEMBER"

    unknown_label = client.post(
        "/api/projects/ATL/tickets", headers=owner_headers, json={"title": "x", "labels": ["ghost"]}
    )
    assert unknown_label.status_code == 422
    assert unknown_label.json()["error"]["code"] == "LABEL_NOT_FOUND"


def test_transition_rules(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers, status="todo")
    moved = client.post(
        f"/api/tickets/{ticket['key']}/transition",
        headers=owner_headers,
        json={"to": "in_progress", "position": 2},
    )
    assert moved.status_code == 200
    body = moved.json()
    assert body["ticket"]["status"] == "in_progress"
    assert body["ticket"]["board_position"] == 2
    assert body["warnings"] == []

    activity = client.get(f"/api/tickets/{ticket['key']}/activity", headers=owner_headers).json()
    change = next(row for row in activity["items"] if row["field"] == "status")
    assert (change["old_value"], change["new_value"]) == ("todo", "in_progress")

    bad = client.post(
        f"/api/tickets/{ticket['key']}/transition", headers=owner_headers, json={"to": "finished"}
    )
    assert bad.status_code == 422


def test_blocked_requires_reason(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers)
    missing = client.post(
        f"/api/tickets/{ticket['key']}/transition", headers=owner_headers, json={"to": "blocked"}
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "BLOCKED_REASON_REQUIRED"

    short = client.post(
        f"/api/tickets/{ticket['key']}/transition",
        headers=owner_headers,
        json={"to": "blocked", "blocked_reason": "no"},
    )
    assert short.status_code == 422

    ok = client.post(
        f"/api/tickets/{ticket['key']}/transition",
        headers=owner_headers,
        json={"to": "blocked", "blocked_reason": "waiting on infra"},
    )
    assert ok.status_code == 200
    assert ok.json()["ticket"]["blocked_reason"] == "waiting on infra"

    moved = client.post(
        f"/api/tickets/{ticket['key']}/transition", headers=owner_headers, json={"to": "todo"}
    )
    assert moved.json()["ticket"]["blocked_reason"] is None


def test_done_sets_closed_at_and_member_cannot_reopen(
    client, owner_headers, member_headers, project_with_member
):
    ticket = make_ticket(client, owner_headers, status="review")
    done = client.post(
        f"/api/tickets/{ticket['key']}/transition", headers=owner_headers, json={"to": "done"}
    )
    assert done.status_code == 200
    assert done.json()["ticket"]["closed_at"] is not None

    denied = client.post(
        f"/api/tickets/{ticket['key']}/transition", headers=member_headers, json={"to": "todo"}
    )
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "REOPEN_FORBIDDEN"

    reopened = client.post(
        f"/api/tickets/{ticket['key']}/transition", headers=owner_headers, json={"to": "review"}
    )
    assert reopened.status_code == 200
    assert reopened.json()["ticket"]["closed_at"] is None


def test_subtasks_and_depth(client, owner_headers, project):
    parent = make_ticket(client, owner_headers, title="Epic")
    sub = make_ticket(client, owner_headers, title="Step", parent_id=parent["key"])
    assert sub["parent_id"] == parent["id"]

    children = client.get(f"/api/tickets/{parent['key']}/children", headers=owner_headers).json()
    assert [c["key"] for c in children["items"]] == [sub["key"]]
    assert client.get(f"/api/tickets/{parent['key']}", headers=owner_headers).json()["children_count"] == 1

    grandchild = client.post(
        "/api/projects/ATL/tickets",
        headers=owner_headers,
        json={"title": "grandchild", "parent_id": sub["key"]},
    )
    assert grandchild.status_code == 422
    assert grandchild.json()["error"]["code"] == "MAX_DEPTH_EXCEEDED"

    self_parent = client.patch(
        f"/api/tickets/{parent['key']}", headers=owner_headers, json={"parent_id": parent["key"]}
    )
    assert self_parent.status_code == 422
    assert self_parent.json()["error"]["code"] == "INVALID_PARENT"


def test_done_with_open_children_warns(client, owner_headers, project):
    parent = make_ticket(client, owner_headers, title="Epic", status="review")
    make_ticket(client, owner_headers, title="Child", parent_id=parent["key"], status="todo")
    resp = client.post(
        f"/api/tickets/{parent['key']}/transition", headers=owner_headers, json={"to": "done"}
    )
    assert resp.status_code == 200
    assert resp.json()["warnings"]


def test_patch_tracks_each_field_and_version(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers, title="Old", priority="low")
    resp = client.patch(
        f"/api/tickets/{ticket['key']}",
        headers=owner_headers,
        json={"title": "New", "priority": "high", "estimate_points": 3},
    )
    assert resp.status_code == 200
    assert resp.json()["version"] == ticket["version"] + 1

    activity = client.get(f"/api/tickets/{ticket['key']}/activity", headers=owner_headers).json()
    fields = {(row["field"], row["old_value"], row["new_value"]) for row in activity["items"]}
    assert ("title", "Old", "New") in fields
    assert any(f == "priority" and n == "high" for f, _o, n in fields)
    assert any(f == "estimate_points" and n == "3" for f, _o, n in fields)
    request_ids = {row["request_id"] for row in activity["items"] if row["field"] == "title"}
    assert request_ids and None not in request_ids


def test_stale_version_conflict(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers, title="Versioned")
    first = client.patch(
        f"/api/tickets/{ticket['key']}",
        headers={**owner_headers, "If-Match": str(ticket["version"])},
        json={"title": "First write"},
    )
    assert first.status_code == 200

    stale = client.patch(
        f"/api/tickets/{ticket['key']}",
        headers={**owner_headers, "If-Match": str(ticket["version"])},
        json={"title": "Second write"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "CONFLICT_STALE"


def test_soft_delete_keeps_numbers(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers, title="Doomed")
    assert client.delete(f"/api/tickets/{ticket['key']}", headers=owner_headers).status_code == 204
    assert client.get(f"/api/tickets/{ticket['key']}", headers=owner_headers).status_code == 404

    nxt = make_ticket(client, owner_headers, title="After delete")
    assert nxt["number"] == 2  # ATL-1 is never reused


def test_noop_patch_does_not_bump_version(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers, title="Same")
    same = client.patch(
        f"/api/tickets/{ticket['key']}", headers=owner_headers, json={"title": "Same"}
    )
    assert same.status_code == 200
    assert same.json()["version"] == ticket["version"]
