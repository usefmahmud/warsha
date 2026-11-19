"""Board, list sorting, My Work and search (Epic D)."""

from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import make_ticket


def test_board_columns_order_and_counts(client, owner_headers, project):
    make_ticket(client, owner_headers, title="b1", status="backlog")
    make_ticket(client, owner_headers, title="t1", status="todo")
    make_ticket(client, owner_headers, title="d1", status="done")

    board = client.get("/api/projects/ATL/board", headers=owner_headers).json()
    assert [c["status"] for c in board["columns"]] == [
        "backlog",
        "todo",
        "in_progress",
        "review",
        "blocked",
        "done",
    ]
    counts = {c["status"]: c["count"] for c in board["columns"]}
    assert counts == {
        "backlog": 1,
        "todo": 1,
        "in_progress": 0,
        "review": 0,
        "blocked": 0,
        "done": 1,
    }
    for column in board["columns"]:
        assert column["count"] == len(column["items"])


def test_board_filters_match_counts(
    client, owner_headers, project_with_member, member, labels
):
    make_ticket(client, owner_headers, title="mine", assignee_username="omar", labels=["backend"])
    make_ticket(client, owner_headers, title="other", labels=["frontend"])

    board = client.get(
        "/api/projects/ATL/board", headers=owner_headers, params={"assignee": "omar"}
    ).json()
    assert sum(c["count"] for c in board["columns"]) == 1

    by_label = client.get(
        "/api/projects/ATL/board", headers=owner_headers, params={"label": "frontend"}
    ).json()
    assert sum(c["count"] for c in by_label["columns"]) == 1


def test_board_tiebreak_by_created_at(client, owner_headers, project):
    first = make_ticket(client, owner_headers, title="first", board_position=1024)
    second = make_ticket(client, owner_headers, title="second", board_position=1024)
    board = client.get("/api/projects/ATL/board", headers=owner_headers).json()
    backlog = next(c for c in board["columns"] if c["status"] == "backlog")
    assert [t["key"] for t in backlog["items"]] == [first["key"], second["key"]]


def test_list_sort_priority_uses_rank_order(client, owner_headers, project):
    for priority in ("low", "urgent", "normal", "high"):
        make_ticket(client, owner_headers, title=priority, priority=priority)

    rows = client.get(
        "/api/projects/ATL/tickets", headers=owner_headers, params={"sort": "-priority"}
    ).json()["items"]
    assert [t["priority"] for t in rows] == ["urgent", "high", "normal", "low"]


def test_list_sort_due_date_nulls_last(client, owner_headers, project):
    make_ticket(client, owner_headers, title="nodate")
    make_ticket(client, owner_headers, title="soon", due_date="2026-11-20")
    make_ticket(client, owner_headers, title="later", due_date="2026-12-01")

    rows = client.get(
        "/api/projects/ATL/tickets", headers=owner_headers, params={"sort": "due_date"}
    ).json()["items"]
    assert [t["title"] for t in rows] == ["soon", "later", "nodate"]


def test_pagination(client, owner_headers, project):
    for i in range(5):
        make_ticket(client, owner_headers, title=f"t{i}")
    page = client.get(
        "/api/projects/ATL/tickets", headers=owner_headers, params={"limit": 2, "offset": 2}
    ).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2
    assert page["limit"] == 2 and page["offset"] == 2


def test_my_work_buckets(client, owner_headers, project_with_member, member_headers):
    today = date.today()
    make_ticket(
        client,
        owner_headers,
        title="overdue",
        assignee_username="omar",
        due_date=str(today - timedelta(days=2)),
    )
    make_ticket(
        client,
        owner_headers,
        title="soon",
        assignee_username="omar",
        due_date=str(today + timedelta(days=1)),
    )
    make_ticket(client, owner_headers, title="plain", assignee_username="omar")
    closed = make_ticket(
        client, owner_headers, title="closed", assignee_username="omar", status="review"
    )
    client.post(f"/api/tickets/{closed['key']}/transition", headers=owner_headers, json={"to": "done"})

    work = client.get("/api/me/work", headers=member_headers).json()
    assert "overdue" in {t["title"] for t in work["overdue"]}
    assert "soon" in {t["title"] for t in work["due_soon"]}
    assert "closed" in {t["title"] for t in work["closed_recent"]}
    assert "closed" not in {t["title"] for t in work["assigned"]}


def test_my_work_includes_mentions(client, owner_headers, project_with_member, member_headers):
    ticket = make_ticket(client, owner_headers)
    client.post(
        f"/api/tickets/{ticket['key']}/comments",
        headers=member_headers,
        json={"body_md": "@youssef please look"},
    )
    work = client.get("/api/me/work", headers=owner_headers).json()
    assert work["mentions"]
    assert work["mentions"][0]["ticket"]["key"] == ticket["key"]
    assert work["mentions"][0]["unread"] is True


def test_search_title_and_description(client, owner_headers, project):
    hit = make_ticket(client, owner_headers, title="Fix RTL board")
    make_ticket(client, owner_headers, title="Unrelated", description_md="rtl flicker in sidebar")

    result = client.get("/api/search", headers=owner_headers, params={"q": "rtl"}).json()
    assert result["total"] == 2
    keys = {item["ticket"]["key"] for item in result["items"]}
    assert hit["key"] in keys
    assert any("<em>" in item["snippet"] for item in result["items"])


def test_search_requires_two_characters(client, owner_headers, project):
    resp = client.get("/api/search", headers=owner_headers, params={"q": "r"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "QUERY_TOO_SHORT"


def test_search_is_scoped_to_membership(client, owner_headers, project, member_headers):
    make_ticket(client, owner_headers, title="secret rtl work")
    result = client.get("/api/search", headers=member_headers, params={"q": "rtl"}).json()
    assert result["total"] == 0


def test_search_normalises_arabic_hamza(client, owner_headers, project):
    make_ticket(client, owner_headers, title="إصلاح الواجهة")
    result = client.get("/api/search", headers=owner_headers, params={"q": "اصلاح"}).json()
    assert result["total"] == 1
