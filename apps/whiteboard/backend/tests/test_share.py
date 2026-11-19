"""Read-only share links: token creation, idempotency, access, revocation."""

from __future__ import annotations

from tests.conftest import rect, scene_with


def test_share_creates_token_and_url(client, board):
    r = client.post(f"/api/boards/{board['id']}/share")
    assert r.status_code == 200
    body = r.json()
    assert body["share_token"]
    assert len(body["share_token"]) >= 20
    assert body["share_url"].endswith(f"/s/{body['share_token']}")


def test_share_is_idempotent(client, board):
    first = client.post(f"/api/boards/{board['id']}/share").json()
    second = client.post(f"/api/boards/{board['id']}/share").json()
    assert first["share_token"] == second["share_token"]


def test_share_token_persisted_on_board(client, board):
    token = client.post(f"/api/boards/{board['id']}/share").json()["share_token"]
    assert client.get(f"/api/boards/{board['id']}").json()["share_token"] == token
    assert client.get("/api/boards").json()[0]["share_token"] == token


def test_read_shared_board_by_token(client, board):
    doc = scene_with(rect(fill="#22d3ee"))
    client.patch(f"/api/boards/{board['id']}", json={"doc": doc})
    token = client.post(f"/api/boards/{board['id']}/share").json()["share_token"]

    r = client.get(f"/api/shared/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == board["id"]
    assert body["name"] == board["name"]
    assert body["doc"] == doc


def test_shared_unknown_token_404(client):
    assert client.get("/api/shared/nope-nope-nope").status_code == 404


def test_share_tokens_are_unique_per_board(client, board):
    other = client.post("/api/boards", json={"name": "تاني"}).json()
    a = client.post(f"/api/boards/{board['id']}/share").json()["share_token"]
    b = client.post(f"/api/boards/{other['id']}/share").json()["share_token"]
    assert a != b
    assert client.get(f"/api/shared/{a}").json()["id"] == board["id"]
    assert client.get(f"/api/shared/{b}").json()["id"] == other["id"]


def test_revoke_share_invalidates_link(client, board):
    token = client.post(f"/api/boards/{board['id']}/share").json()["share_token"]
    assert client.delete(f"/api/boards/{board['id']}/share").status_code == 204
    assert client.get(f"/api/shared/{token}").status_code == 404
    assert client.get(f"/api/boards/{board['id']}").json()["share_token"] is None


def test_share_404_for_missing_board(client):
    assert client.post("/api/boards/nope/share").status_code == 404


def test_deleted_board_kills_share_link(client, board):
    token = client.post(f"/api/boards/{board['id']}/share").json()["share_token"]
    client.delete(f"/api/boards/{board['id']}")
    assert client.get(f"/api/shared/{token}").status_code == 404


def test_shared_view_is_read_only_by_contract(client, board):
    """There is no write endpoint under /api/shared — only GET is routed."""
    token = client.post(f"/api/boards/{board['id']}/share").json()["share_token"]
    assert client.patch(f"/api/shared/{token}", json={"name": "hack"}).status_code in (404, 405)
    assert client.post(f"/api/shared/{token}", json={}).status_code in (404, 405)
