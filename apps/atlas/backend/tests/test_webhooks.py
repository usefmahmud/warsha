"""Webhooks: SSRF guard, HMAC signature, admin-only access (AC-21.x)."""

from __future__ import annotations

import json
from urllib.parse import urlparse

import pytest

from app.errors import APIError
from app.models import Webhook
from app.services.events import sign, validate_webhook_url


def test_ssrf_guard_rejects_private_targets():
    for url in (
        "http://127.0.0.1:9090/hook",
        "http://localhost/hook",
        "http://10.0.0.5/hook",
        "http://169.254.169.254/latest/meta-data",
        "https://192.168.1.10/hook",
    ):
        with pytest.raises(APIError) as exc:
            validate_webhook_url(url, allow_private=False)
        assert exc.value.code in ("PRIVATE_URL_FORBIDDEN", "INVALID_URL")


def test_ssrf_guard_rejects_non_http_schemes():
    from app.errors import APIError

    with pytest.raises(APIError):
        validate_webhook_url("ftp://example.com/hook", allow_private=False)


def test_ssrf_guard_allows_public_and_private_when_opted_in():
    assert validate_webhook_url("https://example.com/hook", allow_private=False)
    assert validate_webhook_url("http://127.0.0.1:9000/hook", allow_private=True)


def test_signature_is_deterministic_hmac_sha256():
    body = b'{"event":"ticket.created"}'
    first = sign("s3cret", body)
    assert first == sign("s3cret", body)
    assert first.startswith("sha256=")
    assert first != sign("other", body)
    assert len(first) == len("sha256=") + 64


def test_webhook_admin_only(client, member_headers):
    assert client.get("/api/webhooks", headers=member_headers).status_code == 403
    resp = client.post(
        "/api/webhooks",
        headers=member_headers,
        json={"url": "https://example.com/h", "events": ["ticket.created"]},
    )
    assert resp.status_code == 403


def test_webhook_crud_with_private_override(client, owner_headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "allow_private_webhooks", True)
    created = client.post(
        "/api/webhooks",
        headers=owner_headers,
        json={"url": "http://127.0.0.1:9/hook", "events": ["ticket.created"]},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["secret"]
    assert body["events"] == ["ticket.created"]

    listed = client.get("/api/webhooks", headers=owner_headers).json()
    assert len(listed) == 1
    assert "secret" not in listed[0]

    patched = client.patch(
        f"/api/webhooks/{body['id']}", headers=owner_headers, json={"active": False}
    )
    assert patched.status_code == 200 and patched.json()["active"] is False

    assert client.delete(f"/api/webhooks/{body['id']}", headers=owner_headers).status_code == 204


def test_webhook_rejects_unknown_event(client, owner_headers, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "allow_private_webhooks", True)
    resp = client.post(
        "/api/webhooks",
        headers=owner_headers,
        json={"url": "http://127.0.0.1:9/hook", "events": ["ticket.exploded"]},
    )
    assert resp.status_code == 422


def test_dispatch_only_matches_subscribed_events(client, owner_headers, project, monkeypatch, db):
    from app.config import settings

    monkeypatch.setattr(settings, "allow_private_webhooks", True)
    created = client.post(
        "/api/webhooks",
        headers=owner_headers,
        json={"url": "http://127.0.0.1:9/hook", "events": ["ticket.done"]},
    ).json()

    ticket = client.post(
        "/api/projects/ATL/tickets", headers=owner_headers, json={"title": "no webhook for me"}
    ).json()
    hook = db.get(Webhook, created["id"])
    assert hook is not None
    assert hook.last_sent_at is None  # ticket.created is not subscribed

    client.post(
        f"/api/tickets/{ticket['key']}/transition", headers=owner_headers, json={"to": "todo"}
    )
    hook = db.get(Webhook, created["id"])
    db.refresh(hook)
    assert hook.last_sent_at is None  # only ticket.done would fire


def test_webhook_payload_shape(monkeypatch):
    """The delivery body is {"event", "data"} and is signed (AC-21.1)."""
    from app.services import events

    captured = {}

    class FakeResponse:
        status_code = 200

    def fake_post(url, content=None, headers=None, timeout=None):
        captured["url"] = url
        captured["body"] = json.loads(content)
        captured["headers"] = headers
        return FakeResponse()

    monkeypatch.setattr(events.httpx, "post", fake_post)
    monkeypatch.setattr(
        events, "SessionLocal", lambda: _FakeSession()
    )
    events.deliver_webhook("hook-1", "ticket.created", {"ticket": {"key": "ATL-1"}})
    assert captured["body"]["event"] == "ticket.created"
    assert captured["headers"]["X-Atlas-Signature"].startswith("sha256=")
    assert urlparse("https://example.com/hook").scheme == "https"


class _FakeHook:
    id = "hook-1"
    url = "https://example.com/hook"
    secret = "s3cret"
    active = True
    failures = 0
    last_status = None
    last_sent_at = None


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def get(self, model, key):
        return _FakeHook()

    def add(self, _obj):
        pass

    def commit(self):
        pass
