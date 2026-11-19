"""Autosave semantics: versioning, optimistic concurrency, doc validation, size guard."""

from __future__ import annotations

from tests.conftest import rect, scene_with


def test_patch_doc_bumps_version_and_updated_at(client, board):
    r = client.patch(
        f"/api/boards/{board['id']}",
        json={"doc": scene_with(rect()), "version": board["version"]},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == board["version"] + 1
    assert len(body["doc"]["objects"]) == 1
    assert body["updated_at"] >= board["updated_at"]


def test_autosave_roundtrip_survives_reread(client, board):
    """The editor's real loop: PATCH the scene, then GET it back unchanged."""
    doc = scene_with(
        rect(fill="#f43f5e", angle=15, scaleX=1.5),
        {"type": "i-text", "text": "مرحبا بالعالم", "left": 40, "top": 60, "fill": "#fff"},
        {"type": "path", "path": [["M", 0, 0], ["L", 10, 10]], "stroke": "#22d3ee"},
    )
    saved = client.patch(f"/api/boards/{board['id']}", json={"doc": doc, "version": 1})
    assert saved.status_code == 200
    fetched = client.get(f"/api/boards/{board['id']}").json()
    assert fetched["doc"] == doc
    assert fetched["doc"]["objects"][1]["text"] == "مرحبا بالعالم"


def test_version_conflict_returns_409_with_server_state(client, board):
    first = client.patch(
        f"/api/boards/{board['id']}", json={"doc": scene_with(rect()), "version": 1}
    )
    assert first.status_code == 200
    stale = client.patch(f"/api/boards/{board['id']}", json={"doc": scene_with(), "version": 1})
    assert stale.status_code == 409
    detail = stale.json()["detail"]
    assert detail["expected_version"] == 2
    assert detail["sent_version"] == 1
    assert detail["board"]["id"] == board["id"]
    # server state was not clobbered by the stale write
    assert len(client.get(f"/api/boards/{board['id']}").json()["doc"]["objects"]) == 1


def test_sequential_saves_with_correct_version_all_succeed(client, board):
    version = board["version"]
    for i in range(1, 6):
        r = client.patch(
            f"/api/boards/{board['id']}",
            json={"doc": scene_with(*[rect(left=j) for j in range(i)]), "version": version},
        )
        assert r.status_code == 200, r.text
        version = r.json()["version"]
    assert version == board["version"] + 5


def test_patch_without_version_skips_concurrency_check(client, board):
    client.patch(f"/api/boards/{board['id']}", json={"doc": scene_with(rect()), "version": 1})
    r = client.patch(f"/api/boards/{board['id']}", json={"doc": scene_with()})
    assert r.status_code == 200
    assert r.json()["doc"]["objects"] == []


def test_patch_rejects_non_object_doc(client, board):
    r = client.patch(f"/api/boards/{board['id']}", json={"doc": ["not", "an", "object"]})
    assert r.status_code == 422


def test_patch_rejects_negative_version(client, board):
    r = client.patch(f"/api/boards/{board['id']}", json={"version": -5})
    assert r.status_code == 422


def test_doc_size_ceiling(client, board):
    huge = scene_with({"type": "path", "path": "M0 0 " + "L1 1 " * 2_000_000})
    r = client.patch(f"/api/boards/{board['id']}", json={"doc": huge})
    assert r.status_code == 413


def test_saved_state_is_visible_through_list_count(client, board):
    client.patch(f"/api/boards/{board['id']}", json={"doc": scene_with(rect(), rect())})
    row = client.get("/api/boards").json()[0]
    assert row["object_count"] == 2
    assert row["version"] == 2
