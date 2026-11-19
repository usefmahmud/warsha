"""Ticket domain logic: atomic numbering, create/update, transitions, soft delete."""

from __future__ import annotations

import logging
import time

from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ..errors import APIError, conflict, forbidden, invalid, not_found
from ..models import (
    MAX_SUBTASK_DEPTH,
    MEMBER_FORBIDDEN_TRANSITIONS,
    Label,
    Project,
    ProjectMember,
    ProjectRole,
    Ticket,
    TicketLabel,
    TicketStatus,
    User,
    UserRole,
    utcnow,
)
from ..schemas import TicketCreate, TicketUpdate
from .events import log_activity, notify
from .mentions import record_mentions

log = logging.getLogger("atlas.tickets")
NUMBERING_RETRIES = 3
POSITION_GAP = 1024.0

TRACKED_FIELDS = (
    "title",
    "description_md",
    "type",
    "priority",
    "assignee_id",
    "due_date",
    "estimate_points",
    "parent_id",
)
NON_NULLABLE_FIELDS = {"title", "type", "priority", "description_md"}


# --- helpers ---------------------------------------------------------------
def is_lead(project: Project, user: User, role: ProjectRole | None) -> bool:
    return user.role in (UserRole.owner, UserRole.admin) or role == ProjectRole.lead


def next_number(db: Session, project_id: str) -> int:
    """Atomic `ticket_seq` bump (PRD §5.2). Numbers are never reused."""
    last_error: Exception | None = None
    for attempt in range(NUMBERING_RETRIES):
        try:
            row = db.execute(
                text(
                    "UPDATE projects SET ticket_seq = ticket_seq + 1 "
                    "WHERE id = :pid RETURNING ticket_seq"
                ),
                {"pid": project_id},
            ).first()
            if row is None:
                raise not_found("PROJECT_NOT_FOUND", "project not found")
            return int(row[0])
        except OperationalError as exc:  # database is locked → retry
            last_error = exc
            db.rollback()
            time.sleep(0.05 * (attempt + 1))
    raise APIError(503, "TRY_AGAIN", f"could not allocate a ticket number: {last_error}")


def next_position(db: Session, project_id: str, status: TicketStatus) -> float:
    current = (
        db.query(func.max(Ticket.board_position))
        .filter(
            Ticket.project_id == project_id,
            Ticket.status == status,
            Ticket.deleted_at.is_(None),
        )
        .scalar()
    )
    return (current or 0.0) + POSITION_GAP


def resolve_assignee(
    db: Session,
    project: Project,
    *,
    user_id: str | None = None,
    username: str | None = None,
) -> User | None:
    if user_id is None and not username:
        return None
    user = None
    if user_id is not None:
        user = db.get(User, user_id)
    elif username:
        user = (
            db.query(User)
            .filter(func.lower(User.username) == username.lower(), User.is_active.is_(True))
            .first()
        )
    if user is None or not user.is_active:
        raise not_found("USER_NOT_FOUND", "assignee not found")
    member = db.get(ProjectMember, {"project_id": project.id, "user_id": user.id})
    if member is None and user.role not in (UserRole.owner, UserRole.admin):
        raise invalid("ASSIGNEE_NOT_MEMBER", "assignee is not a member of this project")
    return user


def resolve_labels(db: Session, project: Project, names: list[str]) -> list[Label]:
    labels: list[Label] = []
    missing: list[str] = []
    for raw in names:
        name = raw.strip().lower()
        if not name:
            continue
        label = (
            db.query(Label)
            .filter(Label.project_id == project.id, func.lower(Label.name) == name)
            .first()
        )
        if label is None:
            missing.append(name)
        elif label not in labels:
            labels.append(label)
    if missing:
        raise invalid(
            "LABEL_NOT_FOUND",
            f"unknown label(s): {', '.join(missing)}",
            {"labels": missing},
        )
    return labels


def resolve_parent(db: Session, project: Project, ref: str | None, this_id: str | None = None) -> Ticket | None:
    if not ref:
        return None
    parent: Ticket | None = None
    if "-" in ref:
        project_key, _, number = ref.rpartition("-")
        if number.isdigit() and project_key.upper() == project.key:
            parent = (
                db.query(Ticket)
                .filter(
                    Ticket.project_id == project.id,
                    Ticket.number == int(number),
                    Ticket.deleted_at.is_(None),
                )
                .first()
            )
    if parent is None:
        parent = db.get(Ticket, ref)
    if parent is None or parent.deleted_at is not None:
        raise invalid("INVALID_PARENT", "parent ticket not found")
    if parent.project_id != project.id:
        raise invalid("INVALID_PARENT", "parent ticket belongs to another project")
    if this_id is not None and parent.id == this_id:
        raise invalid("INVALID_PARENT", "a ticket cannot be its own parent")
    if parent.parent_id is not None:
        raise invalid("MAX_DEPTH_EXCEEDED", f"max subtask depth is {MAX_SUBTASK_DEPTH}")
    return parent


def _set_labels(db: Session, ticket: Ticket, labels: list[Label]) -> None:
    db.query(TicketLabel).filter(TicketLabel.ticket_id == ticket.id).delete(
        synchronize_session=False
    )
    for label in labels:
        db.add(TicketLabel(ticket_id=ticket.id, label_id=label.id))


def _notify_assignee(db: Session, ticket: Ticket, actor: User) -> None:
    if ticket.assignee_id and ticket.assignee_id != actor.id:
        notify(
            db,
            user_id=ticket.assignee_id,
            actor_id=actor.id,
            ticket=ticket,
            type="assigned",
            payload={"ticket_key": ticket.key, "title": ticket.title},
        )


# --- create / update -------------------------------------------------------
def create_ticket(
    db: Session,
    *,
    project: Project,
    actor: User,
    payload: TicketCreate,
    request_id: str | None = None,
) -> tuple[Ticket, bool]:
    """Returns (ticket, created). `created=False` means an idempotent client_ref hit."""
    if payload.client_ref:
        existing = (
            db.query(Ticket)
            .filter(
                Ticket.project_id == project.id,
                Ticket.client_ref == payload.client_ref,
                Ticket.deleted_at.is_(None),
            )
            .first()
        )
        if existing is not None:
            return existing, False
        cross = (
            db.query(Ticket)
            .filter(Ticket.client_ref == payload.client_ref, Ticket.project_id != project.id)
            .first()
        )
        if cross is not None:
            raise conflict(
                "DUPLICATE_CLIENT_REF_CROSS_PROJECT",
                "client_ref already used in another project",
            )

    assignee = resolve_assignee(
        db, project, user_id=payload.assignee_id, username=payload.assignee_username
    )
    labels = resolve_labels(db, project, payload.labels)
    parent = resolve_parent(db, project, payload.parent_id)

    ticket = None
    for attempt in range(NUMBERING_RETRIES):
        number = next_number(db, project.id)
        candidate = Ticket(
            project_id=project.id,
            number=number,
            key=f"{project.key}-{number}",
            title=payload.title,
            description_md=payload.description_md or "",
            type=payload.type,
            priority=payload.priority,
            status=payload.status,
            blocked_reason=None,
            assignee_id=assignee.id if assignee else None,
            reporter_id=actor.id,
            parent_id=parent.id if parent else None,
            due_date=payload.due_date,
            estimate_points=payload.estimate_points,
            board_position=(
                payload.board_position
                if payload.board_position is not None
                else next_position(db, project.id, payload.status)
            ),
            client_ref=payload.client_ref,
            closed_at=utcnow() if payload.status == TicketStatus.done else None,
        )
        try:
            db.add(candidate)
            db.flush()
            ticket = candidate
            break
        except IntegrityError as exc:  # pragma: no cover - safety net (AC-08.3)
            db.rollback()
            log.warning("ticket number race (attempt %s): %s", attempt + 1, exc)
            if attempt == NUMBERING_RETRIES - 1:
                raise APIError(503, "TRY_AGAIN", "ticket numbering conflict, retry") from None

    assert ticket is not None
    if labels:
        _set_labels(db, ticket, labels)

    log_activity(
        db,
        project_id=project.id,
        ticket_id=ticket.id,
        actor_id=actor.id,
        action="created",
        field="status",
        new=ticket.status,
        request_id=request_id,
    )
    if ticket.description_md:
        record_mentions(db, ticket=ticket, actor=actor, text=ticket.description_md)
    _notify_assignee(db, ticket, actor)
    db.flush()
    return ticket, True


def ensure_version(ticket: Ticket, expected: int | None) -> None:
    """Optimistic concurrency (AC-10.6). Accepts If-Match style versions."""
    if expected is not None and int(expected) != ticket.version:
        raise conflict(
            "CONFLICT_STALE",
            "ticket was modified by someone else — refresh and retry",
            {"current_version": ticket.version},
        )


def update_ticket(
    db: Session,
    *,
    ticket: Ticket,
    actor: User,
    payload: TicketUpdate,
    request_id: str | None = None,
    expected_version: int | None = None,
) -> list[dict]:
    ensure_version(ticket, expected_version if expected_version is not None else payload.version)
    project = ticket.project
    data = payload.model_dump(exclude_unset=True)
    data.pop("version", None)
    changes: list[dict] = []

    if "assignee_username" in data:
        username = data.pop("assignee_username")
        data["assignee_id"] = None
        if username:
            resolved = resolve_assignee(db, project, username=username)
            data["assignee_id"] = resolved.id if resolved else None
    elif "assignee_id" in data:
        if data["assignee_id"] is None:
            data["assignee_id"] = None
        else:
            data["assignee_id"] = resolve_assignee(
                db, project, user_id=data["assignee_id"]
            ).id

    if "labels" in data:
        names = data.pop("labels") or []
        labels = resolve_labels(db, project, names)
        current = sorted(link.label.name for link in ticket.label_links)
        wanted = sorted(lb.name for lb in labels)
        if current != wanted:
            _set_labels(db, ticket, labels)
            changes.append({"field": "labels", "old": ",".join(current), "new": ",".join(wanted)})

    if "parent_id" in data:
        parent = resolve_parent(db, project, data["parent_id"], this_id=ticket.id)
        data["parent_id"] = parent.id if parent else None

    for field in TRACKED_FIELDS:
        if field not in data:
            continue
        new_value = data[field]
        old_value = getattr(ticket, field)
        if new_value is None and field in NON_NULLABLE_FIELDS:
            continue
        if isinstance(new_value, str) and field in ("title", "description_md"):
            new_value = new_value.strip()
        if new_value == old_value:
            continue
        setattr(ticket, field, new_value)
        changes.append({"field": field, "old": old_value, "new": new_value})

    if (
        data.get("board_position") is not None
        and ticket.board_position != data["board_position"]
    ):
        ticket.board_position = data["board_position"]
        changes.append(
            {"field": "board_position", "old": None, "new": data["board_position"]}
        )

    if not changes:
        return []

    ticket.version = (ticket.version or 1) + 1
    ticket.updated_at = utcnow()
    db.add(ticket)

    for change in changes:
        log_activity(
            db,
            project_id=project.id,
            ticket_id=ticket.id,
            actor_id=actor.id,
            action="updated",
            field=change["field"],
            old=change["old"],
            new=change["new"],
            request_id=request_id,
        )

    if any(c["field"] == "assignee_id" for c in changes):
        _notify_assignee(db, ticket, actor)
    if any(c["field"] == "description_md" for c in changes) and ticket.description_md:
        record_mentions(db, ticket=ticket, actor=actor, text=ticket.description_md)
    db.flush()
    return changes


# --- transitions -----------------------------------------------------------
def transition_ticket(
    db: Session,
    *,
    ticket: Ticket,
    actor: User,
    to: TicketStatus,
    role: ProjectRole | None,
    blocked_reason: str | None = None,
    position: float | None = None,
    expected_version: int | None = None,
    request_id: str | None = None,
) -> tuple[Ticket, list[str]]:
    ensure_version(ticket, expected_version)
    warnings: list[str] = []
    lead = is_lead(ticket.project, actor, role)
    old_status = ticket.status

    if old_status == to and position is None:
        return ticket, warnings

    if (old_status, to) in MEMBER_FORBIDDEN_TRANSITIONS and not lead:
        raise forbidden("REOPEN_FORBIDDEN", "only admins can reopen a done ticket")

    reason = (blocked_reason or "").strip() or None
    if to == TicketStatus.blocked and reason is None:
        raise invalid("BLOCKED_REASON_REQUIRED", "blocked_reason is required for blocked")
    if to != TicketStatus.blocked:
        reason = None

    if to == TicketStatus.done:
        open_children = (
            db.query(func.count(Ticket.id))
            .filter(
                Ticket.parent_id == ticket.id,
                Ticket.status != TicketStatus.done,
                Ticket.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )
        if open_children:
            warnings.append(f"{open_children} open subtask(s) will remain open")

    ticket.status = to
    ticket.blocked_reason = reason
    if position is not None:
        ticket.board_position = position
    elif old_status != to:
        ticket.board_position = next_position(db, ticket.project_id, to)

    if to == TicketStatus.done:
        ticket.closed_at = utcnow()
    elif old_status == TicketStatus.done:
        ticket.closed_at = None

    ticket.version = (ticket.version or 1) + 1
    ticket.updated_at = utcnow()
    db.add(ticket)

    if old_status != to:
        log_activity(
            db,
            project_id=ticket.project_id,
            ticket_id=ticket.id,
            actor_id=actor.id,
            action="status_changed",
            field="status",
            old=old_status,
            new=to,
            request_id=request_id,
        )
        if ticket.assignee_id and ticket.assignee_id != actor.id:
            notify(
                db,
                user_id=ticket.assignee_id,
                actor_id=actor.id,
                ticket=ticket,
                type="status",
                payload={
                    "ticket_key": ticket.key,
                    "from": old_status.value,
                    "to": to.value,
                },
            )
    if reason is not None:
        log_activity(
            db,
            project_id=ticket.project_id,
            ticket_id=ticket.id,
            actor_id=actor.id,
            action="blocked_reason",
            field="blocked_reason",
            new=reason,
            request_id=request_id,
        )
    db.flush()
    return ticket, warnings


def soft_delete(db: Session, *, ticket: Ticket, actor: User, request_id: str | None = None) -> None:
    ticket.deleted_at = utcnow()
    ticket.updated_at = utcnow()
    ticket.version = (ticket.version or 1) + 1
    db.add(ticket)
    log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=actor.id,
        action="deleted",
        field="deleted_at",
        new=ticket.key,
        request_id=request_id,
    )
    db.flush()
