"""API behaviour: CRUD, toggle, filters, validation, error envelope."""

from __future__ import annotations


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"] == "sqlite"


def test_root_health_alias(client):
    """Container healthchecks probe /health (no /api prefix)."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_meta_priorities(client):
    r = client.get("/api/meta")
    assert r.status_code == 200
    values = [p["value"] for p in r.json()["priorities"]]
    assert values == ["high", "normal", "low"]


def test_list_empty(client):
    r = client.get("/api/todos")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["count"] == 0
    assert body["open_count"] == 0
    assert body["done_count"] == 0


def test_create_minimal(client):
    r = client.post("/api/todos", json={"title": "اشتري لبن"})
    assert r.status_code == 201
    todo = r.json()
    assert todo["title"] == "اشتري لبن"
    assert todo["done"] is False
    assert todo["priority"] == "normal"
    assert todo["notes"] is None
    assert todo["due_date"] is None
    assert todo["id"]
    assert todo["created_at"].endswith("Z")
    assert todo["updated_at"].endswith("Z")


def test_create_full(client):
    r = client.post(
        "/api/todos",
        json={
            "title": "مراجعة الكود",
            "notes": "راجع الـbackend",
            "priority": "high",
            "due_date": "2026-12-01",
        },
    )
    assert r.status_code == 201
    todo = r.json()
    assert todo["priority"] == "high"
    assert todo["notes"] == "راجع الـbackend"
    assert todo["due_date"] == "2026-12-01"


def test_create_trims_title(client):
    r = client.post("/api/todos", json={"title": "   مسافات   "})
    assert r.status_code == 201
    assert r.json()["title"] == "مسافات"


def test_get_one(client, make_todo):
    todo = make_todo(title="واحدة")
    r = client.get(f"/api/todos/{todo['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == todo["id"]


def test_get_missing_returns_envelope(client):
    r = client.get("/api/todos/does-not-exist")
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "TODO_NOT_FOUND"
    assert "does-not-exist" in err["message"]
    assert err["request_id"].startswith("req_")


def test_patch_title(client, make_todo):
    todo = make_todo(title="قديم")
    r = client.patch(f"/api/todos/{todo['id']}", json={"title": "جديد"})
    assert r.status_code == 200
    assert r.json()["title"] == "جديد"


def test_patch_partial_keeps_other_fields(client, make_todo):
    todo = make_todo(title="ثابت", notes="ملاحظة", priority="high")
    r = client.patch(f"/api/todos/{todo['id']}", json={"notes": "متغير"})
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "ثابت"
    assert body["notes"] == "متغير"
    assert body["priority"] == "high"


def test_patch_can_clear_notes(client, make_todo):
    todo = make_todo(title="بملاحظة", notes="هتتشال")
    r = client.patch(f"/api/todos/{todo['id']}", json={"notes": None})
    assert r.status_code == 200
    assert r.json()["notes"] is None


def test_patch_empty_body_rejected(client, make_todo):
    todo = make_todo()
    r = client.patch(f"/api/todos/{todo['id']}", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "EMPTY_PATCH"


def test_patch_done_flag(client, make_todo):
    todo = make_todo()
    r = client.patch(f"/api/todos/{todo['id']}", json={"done": True})
    assert r.status_code == 200
    assert r.json()["done"] is True


def test_patch_missing_404(client):
    r = client.patch("/api/todos/nope", json={"title": "x"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "TODO_NOT_FOUND"


def test_toggle_flips_both_ways(client, make_todo):
    todo = make_todo()
    assert todo["done"] is False
    r1 = client.post(f"/api/todos/{todo['id']}/toggle")
    assert r1.status_code == 200
    assert r1.json()["done"] is True
    r2 = client.post(f"/api/todos/{todo['id']}/toggle")
    assert r2.json()["done"] is False


def test_toggle_missing_404(client):
    r = client.post("/api/todos/nope/toggle")
    assert r.status_code == 404


def test_delete_removes(client, make_todo):
    todo = make_todo()
    r = client.delete(f"/api/todos/{todo['id']}")
    assert r.status_code == 204
    assert r.content == b""
    assert client.get(f"/api/todos/{todo['id']}").status_code == 404


def test_delete_missing_404(client):
    r = client.delete("/api/todos/nope")
    assert r.status_code == 404


# --- filters ---------------------------------------------------------------


def test_filter_done(client, make_todo):
    a = make_todo(title="مفتوحة")
    b = make_todo(title="منجزة")
    client.post(f"/api/todos/{b['id']}/toggle")

    open_only = client.get("/api/todos", params={"done": "false"}).json()
    done_only = client.get("/api/todos", params={"done": "true"}).json()

    assert [t["id"] for t in open_only["items"]] == [a["id"]]
    assert [t["id"] for t in done_only["items"]] == [b["id"]]
    assert done_only["count"] == 1
    assert open_only["count"] == 1
    assert done_only["open_count"] == 1  # global counter
    assert done_only["done_count"] == 1


def test_filter_q_matches_title_and_notes(client, make_todo):
    make_todo(title="تقرير المبيعات")
    make_todo(title="مكالمة", notes="عن تقرير الربع الثالث")
    make_todo(title="شيء تاني")

    r = client.get("/api/todos", params={"q": "تقرير"}).json()
    assert r["count"] == 2


def test_filter_q_is_case_insensitive_for_latin(client, make_todo):
    make_todo(title="Deploy the API")
    r = client.get("/api/todos", params={"q": "deploy"}).json()
    assert r["count"] == 1


def test_filter_q_no_match(client, make_todo):
    make_todo(title="حاجة")
    r = client.get("/api/todos", params={"q": "zzz"}).json()
    assert r["count"] == 0
    assert r["open_count"] == 1  # counters stay global


def test_filter_priority(client, make_todo):
    make_todo(title="عاجل", priority="high")
    make_todo(title="عادي", priority="normal")
    r = client.get("/api/todos", params={"priority": "high"}).json()
    assert r["count"] == 1
    assert r["items"][0]["title"] == "عاجل"


def test_filter_invalid_priority_rejected(client):
    r = client.get("/api/todos", params={"priority": "urgent"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_sorting_open_first_then_priority(client, make_todo):
    low = make_todo(title="منخفضة", priority="low")
    high = make_todo(title="عالية", priority="high")
    done = make_todo(title="منجزة", priority="high")
    client.post(f"/api/todos/{done['id']}/toggle")

    items = client.get("/api/todos").json()["items"]
    ids = [t["id"] for t in items]
    assert ids.index(high["id"]) < ids.index(low["id"])
    assert ids[-1] == done["id"]  # done sinks to the bottom


def test_limit(client, make_todo):
    for i in range(5):
        make_todo(title=f"مهمة {i}")
    r = client.get("/api/todos", params={"limit": 2}).json()
    assert r["count"] == 2
    assert r["open_count"] == 5


# --- validation ------------------------------------------------------------


def test_create_empty_title_422(client):
    r = client.post("/api/todos", json={"title": ""})
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["details"][0]["field"] == "title"


def test_create_whitespace_title_422(client):
    r = client.post("/api/todos", json={"title": "     "})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_create_title_too_long_422(client):
    r = client.post("/api/todos", json={"title": "x" * 201})
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["field"] == "title"


def test_create_title_at_limit_ok(client):
    r = client.post("/api/todos", json={"title": "x" * 200})
    assert r.status_code == 201


def test_create_missing_title_422(client):
    r = client.post("/api/todos", json={"notes": "بدون عنوان"})
    assert r.status_code == 422
    assert r.json()["error"]["details"][0]["field"] == "title"


def test_create_bad_priority_422(client):
    r = client.post("/api/todos", json={"title": "x", "priority": "critical"})
    assert r.status_code == 422


def test_create_unknown_field_rejected(client):
    r = client.post("/api/todos", json={"title": "x", "unknown": 1})
    assert r.status_code == 422


def test_bad_due_date_422(client):
    r = client.post("/api/todos", json={"title": "x", "due_date": "not-a-date"})
    assert r.status_code == 422


def test_patch_title_too_long_422(client, make_todo):
    todo = make_todo()
    r = client.patch(f"/api/todos/{todo['id']}", json={"title": "y" * 250})
    assert r.status_code == 422


def test_request_id_echoed(client):
    r = client.get("/api/todos", headers={"X-Request-Id": "req_abcdef12"})
    assert r.headers["X-Request-Id"] == "req_abcdef12"


def test_cors_preflight(client):
    r = client.options(
        "/api/todos",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_unknown_api_route_404_envelope(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert "error" in r.json()
