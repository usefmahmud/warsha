"""Activity log, notifications and outbound webhooks (PRD §7.10, AC-21.x)."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..errors import invalid
from ..models import Activity, Notification, Ticket, User, Webhook

log = logging.getLogger("atlas.events")
WEBHOOK_TIMEOUT = 5.0
WEBHOOK_FAILURE_LIMIT = 3


def _fmt(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    if hasattr(value, "value"):
        return str(value.value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def log_activity(
    db: Session,
    *,
    project_id: str,
    actor_id: str | None,
    action: str,
    ticket_id: str | None = None,
    field: str | None = None,
    old: object = None,
    new: object = None,
    request_id: str | None = None,
) -> Activity:
    row = Activity(
        project_id=project_id,
        ticket_id=ticket_id,
        actor_id=actor_id,
        action=action,
        field=field,
        old_value=_fmt(old),
        new_value=_fmt(new),
        request_id=request_id,
    )
    db.add(row)
    return row


def notify(
    db: Session,
    *,
    user_id: str | None,
    type: str,
    payload: dict,
    actor_id: str | None = None,
    ticket: Ticket | None = None,
) -> Notification | None:
    if not user_id or user_id == actor_id:  # AC-20.4: never notify yourself
        return None
    row = Notification(
        user_id=user_id,
        actor_id=actor_id,
        ticket_id=ticket.id if ticket else None,
        type=type,
        payload=payload,
    )
    db.add(row)
    return row


# --- webhooks --------------------------------------------------------------
def validate_webhook_url(url: str, allow_private: bool) -> str:
    """AC-21.4: http(s) only, and no SSRF into private ranges unless allowed."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise invalid("INVALID_URL", "webhook url must be http(s)")
    if allow_private:
        return url
    host = parsed.hostname
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        raise invalid("INVALID_URL", f"cannot resolve host {host!r}") from None
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        if (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_reserved
            or address.is_multicast
        ):
            raise invalid("PRIVATE_URL_FORBIDDEN", "private/internal webhook targets are blocked")
    return url


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def deliver_webhook(webhook_id: str, event: str, data: dict) -> None:
    """Best-effort delivery in its own session; never breaks the request path (AC-21.2)."""
    with SessionLocal() as db:
        hook = db.get(Webhook, webhook_id)
        if hook is None or not hook.active:
            return
        body = json.dumps({"event": event, "data": data}, ensure_ascii=False).encode()
        headers = {
            "Content-Type": "application/json",
            "X-Atlas-Event": event,
            "X-Atlas-Signature": sign(hook.secret, body),
        }
        status_code: int | None = None
        try:
            response = httpx.post(hook.url, content=body, headers=headers, timeout=WEBHOOK_TIMEOUT)
            status_code = response.status_code
            ok = 200 <= response.status_code < 300
        except Exception as exc:  # noqa: BLE001 - outbound failures are non-fatal
            log.warning("webhook %s failed: %s", hook.id, exc)
            ok = False

        hook.last_status = status_code
        hook.last_sent_at = datetime.now(UTC).replace(tzinfo=None)
        if ok:
            hook.failures = 0
        else:
            hook.failures = (hook.failures or 0) + 1
            if hook.failures >= WEBHOOK_FAILURE_LIMIT:
                hook.active = False  # AC-21.3
        db.add(hook)
        db.commit()


def dispatch(db: Session, event: str, data: dict, project_id: str | None, background) -> None:
    """Queue every matching active webhook onto the response's background tasks."""
    hooks = (
        db.query(Webhook)
        .filter(Webhook.active.is_(True))
        .filter((Webhook.project_id.is_(None)) | (Webhook.project_id == project_id))
        .all()
    )
    for hook in hooks:
        if event not in (hook.events or []):
            continue
        background.add_task(deliver_webhook, hook.id, event, data)


def event_payload(ticket: Ticket, actor: User | None, request_id: str | None = None) -> dict:
    return {
        "ticket": {
            "id": ticket.id,
            "key": ticket.key,
            "title": ticket.title,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
            "type": ticket.type.value,
            "assignee_id": ticket.assignee_id,
            "project_id": ticket.project_id,
        },
        "actor": {"id": actor.id, "username": actor.username} if actor else None,
        "timestamp": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "request_id": request_id,
    }


def timed(fn):  # small helper used by the webhook /test endpoint
    started = time.perf_counter()
    result = fn()
    return result, int((time.perf_counter() - started) * 1000)
