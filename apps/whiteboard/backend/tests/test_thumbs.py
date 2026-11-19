"""Thumbnail endpoint used by the board cards."""

from __future__ import annotations

import base64

from tests.conftest import rect, scene_with

# 1x1 transparent PNG
PNG_1x1 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AH7LZ8AAAAASUVORK5CYII="
)


def test_thumb_served_as_png(client, board):
    client.patch(f"/api/boards/{board['id']}", json={"thumb": PNG_1x1})
    r = client.get(f"/api/boards/{board['id']}/thumb")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content.startswith(b"\x89PNG")


def test_thumb_404_when_absent(client, board):
    assert client.get(f"/api/boards/{board['id']}/thumb").status_code == 404


def test_thumb_404_for_missing_board(client):
    assert client.get("/api/boards/nope/thumb").status_code == 404


def test_thumb_survives_scene_update(client, board):
    client.patch(f"/api/boards/{board['id']}", json={"thumb": PNG_1x1, "doc": scene_with(rect())})
    assert client.get(f"/api/boards/{board['id']}/thumb").status_code == 200
    assert len(client.get(f"/api/boards/{board['id']}").json()["doc"]["objects"]) == 1


def test_thumb_payload_is_base64(client, board):
    client.patch(f"/api/boards/{board['id']}", json={"thumb": PNG_1x1})
    raw = client.get(f"/api/boards/{board['id']}/thumb").content
    assert base64.b64encode(raw).decode().startswith("iVBORw0KGgo")
