"""Comments, mentions and notifications (Epic C/E)."""

from __future__ import annotations

from tests.conftest import make_ticket


def _comment(client, headers, ticket_key: str, body: str):
    resp = client.post(f"/api/tickets/{ticket_key}/comments", headers=headers, json={"body_md": body})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_comment_with_mention_creates_one_notification(
    client, owner_headers, project_with_member, member_headers
):
    ticket = make_ticket(client, owner_headers)
    comment = _comment(
        client, member_headers, ticket["key"], "يا @youssef شوف دي، و@youssef تاني"
    )
    assert [u["username"] for u in comment["mentions"]] == ["youssef"]

    notes = client.get("/api/notifications", headers=owner_headers).json()
    mentions = [n for n in notes["items"] if n["type"] == "mention"]
    assert len(mentions) == 1
    assert mentions[0]["ticket_key"] == ticket["key"]
    assert mentions[0]["read_at"] is None

    count = client.get("/api/notifications/unread_count", headers=owner_headers).json()
    assert count["count"] == 1


def test_unknown_and_self_mentions_are_silent(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers)
    comment = _comment(
        client, owner_headers, ticket["key"], "hi @ghost_user and @youssef"
    )
    assert [u["username"] for u in comment["mentions"]] == ["youssef"]
    assert client.get("/api/notifications/unread_count", headers=owner_headers).json()["count"] == 0


def test_code_spans_and_links_do_not_mention(client, owner_headers, project_with_member):
    ticket = make_ticket(client, owner_headers)
    comment = _comment(
        client,
        owner_headers,
        ticket["key"],
        "`@omar` in code\n```\n@omar\n```\n[link @omar](https://x.dev/@omar)",
    )
    assert comment["mentions"] == []
    assert client.get("/api/notifications/unread_count", headers=owner_headers).json()["count"] == 0


def test_description_mentions_notify(client, owner_headers, project_with_member, member):
    make_ticket(client, owner_headers, title="Review", description_md="ping @omar for specs")
    count = client.get(
        "/api/notifications/unread_count", headers={"Authorization": f"Bearer {member['access_token']}"}
    ).json()["count"]
    assert count >= 1


def test_comment_edit_and_soft_delete(client, owner_headers, project_with_member, member_headers):
    ticket = make_ticket(client, owner_headers)
    comment = _comment(client, member_headers, ticket["key"], "first version")

    edited = client.patch(
        f"/api/comments/{comment['id']}",
        headers=member_headers,
        json={"body_md": "second version"},
    )
    assert edited.status_code == 200
    assert edited.json()["body_md"] == "second version"
    assert edited.json()["edited_at"] is not None

    denied = client.patch(
        f"/api/comments/{comment['id']}", headers=owner_headers, json={"body_md": "hijack"}
    )
    assert denied.status_code == 200  # owner is a project lead → may moderate

    assert client.delete(f"/api/comments/{comment['id']}", headers=member_headers).status_code == 204
    rows = client.get(f"/api/tickets/{ticket['key']}/comments", headers=owner_headers).json()
    assert rows["items"][0]["body_md"] == "[deleted]"


def test_member_cannot_delete_others_comment(client, owner_headers, project_with_member, member_headers):
    ticket = make_ticket(client, owner_headers)
    comment = _comment(client, owner_headers, ticket["key"], "mine")
    resp = client.delete(f"/api/comments/{comment['id']}", headers=member_headers)
    assert resp.status_code == 403


def test_comments_are_ordered_and_paginated(client, owner_headers, project):
    ticket = make_ticket(client, owner_headers)
    for i in range(3):
        _comment(client, owner_headers, ticket["key"], f"c{i}")
    page = client.get(
        f"/api/tickets/{ticket['key']}/comments", headers=owner_headers, params={"limit": 2}
    ).json()
    assert page["total"] == 3
    assert [c["body_md"] for c in page["items"]] == ["c0", "c1"]


def test_notification_read_flow(client, owner_headers, project_with_member, member_headers):
    # clear the "you were added to the project" notification from the fixture
    client.post("/api/notifications/read-all", headers=member_headers)
    assert client.get("/api/notifications/unread_count", headers=member_headers).json()["count"] == 0

    make_ticket(client, owner_headers, assignee_username="omar")
    note = client.get(
        "/api/notifications", headers=member_headers, params={"type_filter": "assigned"}
    ).json()["items"][0]
    assert note["type"] == "assigned"
    assert client.get("/api/notifications/unread_count", headers=member_headers).json()["count"] == 1

    assert (
        client.post(f"/api/notifications/{note['id']}/read", headers=member_headers).status_code
        == 204
    )
    assert client.get("/api/notifications/unread_count", headers=member_headers).json()["count"] == 0

    make_ticket(client, owner_headers, title="Second", assignee_username="omar")
    bulk = client.post("/api/notifications/read-all", headers=member_headers)
    assert bulk.status_code == 200 and bulk.json()["updated"] == 1
    assert client.get("/api/notifications/unread_count", headers=member_headers).json()["count"] == 0


def test_self_assignment_creates_no_notification(client, owner_headers, project):
    make_ticket(client, owner_headers, assignee_username="youssef")
    assert client.get("/api/notifications/unread_count", headers=owner_headers).json()["count"] == 0


def test_my_mentions_endpoint(client, owner_headers, project_with_member, member_headers):
    ticket = make_ticket(client, owner_headers)
    _comment(client, member_headers, ticket["key"], "@youssef check")
    mentions = client.get("/api/me/mentions", headers=owner_headers).json()
    assert mentions["total"] == 1
    assert mentions["items"][0]["payload"]["ticket_key"] == ticket["key"]
