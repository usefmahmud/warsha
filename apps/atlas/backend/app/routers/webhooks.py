"""Outbound webhooks admin API (PRD §7.10, AC-21.x)."""

from __future__ import annotations

import secrets
import time

import httpx
from fastapi import APIRouter, status

from ..config import settings
from ..deps import AdminUser, DbDep
from ..errors import not_found
from ..models import Webhook
from ..schemas import (
    WebhookCreate,
    WebhookCreated,
    WebhookOut,
    WebhookTestResult,
    WebhookUpdate,
)
from ..services.events import sign, validate_webhook_url

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _out(hook: Webhook) -> WebhookOut:
    return WebhookOut(
        id=hook.id,
        url=hook.url,
        events=list(hook.events or []),
        project_id=hook.project_id,
        active=hook.active,
        failures=hook.failures,
        last_status=hook.last_status,
        last_sent_at=hook.last_sent_at,
        created_at=hook.created_at,
    )


@router.get("", response_model=list[WebhookOut])
def list_webhooks(db: DbDep, admin: AdminUser) -> list[WebhookOut]:
    return [_out(h) for h in db.query(Webhook).order_by(Webhook.created_at.desc()).all()]


@router.post("", response_model=WebhookCreated, status_code=status.HTTP_201_CREATED)
def create_webhook(payload: WebhookCreate, db: DbDep, admin: AdminUser) -> WebhookCreated:
    url = validate_webhook_url(payload.url, settings.allow_private_webhooks)
    hook = Webhook(
        url=url,
        events=payload.events,
        project_id=payload.project_id,
        secret=secrets.token_urlsafe(32),
        active=payload.active,
    )
    db.add(hook)
    db.commit()
    db.refresh(hook)
    return WebhookCreated(**_out(hook).model_dump(), secret=hook.secret)


@router.patch("/{webhook_id}", response_model=WebhookOut)
def update_webhook(
    webhook_id: str, payload: WebhookUpdate, db: DbDep, admin: AdminUser
) -> WebhookOut:
    hook = db.get(Webhook, webhook_id)
    if hook is None:
        raise not_found("NOT_FOUND", "webhook not found")
    data = payload.model_dump(exclude_unset=True)
    if data.get("url"):
        hook.url = validate_webhook_url(data["url"], settings.allow_private_webhooks)
    if data.get("events") is not None:
        hook.events = payload.events
    if data.get("active") is not None:
        hook.active = payload.active
        if payload.active:
            hook.failures = 0
    db.add(hook)
    db.commit()
    db.refresh(hook)
    return _out(hook)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(webhook_id: str, db: DbDep, admin: AdminUser) -> None:
    hook = db.get(Webhook, webhook_id)
    if hook is None:
        raise not_found("NOT_FOUND", "webhook not found")
    db.delete(hook)
    db.commit()


@router.post("/{webhook_id}/test", response_model=WebhookTestResult)
def test_webhook(webhook_id: str, db: DbDep, admin: AdminUser) -> WebhookTestResult:
    hook = db.get(Webhook, webhook_id)
    if hook is None:
        raise not_found("NOT_FOUND", "webhook not found")
    import json

    body = json.dumps({"event": "webhook.test", "data": {"hook_id": hook.id}}).encode()
    headers = {
        "Content-Type": "application/json",
        "X-Atlas-Event": "webhook.test",
        "X-Atlas-Signature": sign(hook.secret, body),
    }
    started = time.perf_counter()
    try:
        response = httpx.post(hook.url, content=body, headers=headers, timeout=5.0)
        duration = int((time.perf_counter() - started) * 1000)
        hook.last_status = response.status_code
        hook.last_sent_at = __import__("datetime").datetime.utcnow()
        db.add(hook)
        db.commit()
        return WebhookTestResult(
            status_code=response.status_code,
            duration_ms=duration,
            ok=200 <= response.status_code < 300,
        )
    except Exception as exc:  # noqa: BLE001
        duration = int((time.perf_counter() - started) * 1000)
        return WebhookTestResult(status_code=None, duration_ms=duration, ok=False, error=str(exc))
