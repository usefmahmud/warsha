"""Boards CRUD — create, list, read, rename/recolour, delete."""

from __future__ import annotations

from tests.conftest import SCENE, rect, scene_with


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["version"] == "1.0.0"


def test_create_board_defaults(client):
    r = client.post("/api/boards", json={})
    assert r.status_code == 201
    body = r.json()
    assert body["id"]
    assert body["name"] == "بورد جديد"
    assert body["version"] == 1
    assert body["doc"]["objects"] == []
    assert body["share_token"] is None
    assert body["created_at"].endswith("Z")
    assert body["updated_at"].endswith("Z")


def test_create_board_with_name_colour_and_doc(client):
    doc = scene_with(rect())
    r = client.post("/api/boards", json={"name": "مخطط", "color": "#f43f5e", "doc": doc})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "مخطط"
    assert body["color"] == "#f43f5e"
    assert body["doc"] == doc


def test_create_board_rejects_blank_name(client):
    r = client.post("/api/boards", json={"name": "   "})
    assert r.status_code == 422


def test_create_board_rejects_long_name(client):
    r = client.post("/api/boards", json={"name": "x" * 200})
    assert r.status_code == 422


def test_list_boards_empty(client):
    r = client.get("/api/boards")
    assert r.status_code == 200
    assert r.json() == []


def test_list_boards_is_newest_first_and_omits_doc(client, board):
    second = client.post("/api/boards", json={"name": "تاني"}).json()
    r = client.get("/api/boards")
    assert r.status_code == 200
    rows = r.json()
    assert [row["id"] for row in rows][:2] == [second["id"], board["id"]]
    assert "doc" not in rows[0]  # summary payload stays light
    assert rows[0]["object_count"] == 0
    assert rows[0]["has_thumb"] is False


def test_list_boards_object_count(client, board):
    client.patch(
        f"/api/boards/{board['id']}",
        json={"doc": scene_with(rect(), rect(left=200))},
    )
    rows = client.get("/api/boards").json()
    assert rows[0]["object_count"] == 2


def test_get_board(client, board):
    r = client.get(f"/api/boards/{board['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == board["id"]
    assert r.json()["doc"] == SCENE


def test_get_board_404(client):
    r = client.get("/api/boards/does-not-exist")
    assert r.status_code == 404


def test_rename_board(client, board):
    r = client.patch(f"/api/boards/{board['id']}", json={"name": "اسم جديد"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "اسم جديد"
    assert body["version"] == board["version"] + 1


def test_patch_without_changes_keeps_version(client, board):
    r = client.patch(f"/api/boards/{board['id']}", json={"name": board["name"]})
    assert r.status_code == 200
    assert r.json()["version"] == board["version"]


def test_patch_404(client):
    assert client.patch("/api/boards/nope", json={"name": "x"}).status_code == 404


def test_delete_board(client, board):
    assert client.delete(f"/api/boards/{board['id']}").status_code == 204
    assert client.get(f"/api/boards/{board['id']}").status_code == 404
    assert client.get("/api/boards").json() == []


def test_delete_board_404(client):
    assert client.delete("/api/boards/nope").status_code == 404


def test_thumb_saved_and_flagged_in_list(client, board):
    thumb = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg=="
    r = client.patch(f"/api/boards/{board['id']}", json={"thumb": thumb})
    assert r.status_code == 200
    assert r.json()["thumb"] == thumb
    assert client.get("/api/boards").json()[0]["has_thumb"] is True
