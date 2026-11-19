"""Query builders: ticket filters, sorting, and text search helpers."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Query, Session

from ..models import (
    Label,
    ProjectMember,
    Ticket,
    TicketLabel,
    TicketPriority,
    TicketStatus,
    TicketType,
    User,
)

PRIORITY_ORDER = case(
    (Ticket.priority == TicketPriority.low, 0),
    (Ticket.priority == TicketPriority.normal, 1),
    (Ticket.priority == TicketPriority.high, 2),
    else_=3,
)

STATUS_ORDER_CASE = case(
    (Ticket.status == TicketStatus.backlog, 0),
    (Ticket.status == TicketStatus.todo, 1),
    (Ticket.status == TicketStatus.in_progress, 2),
    (Ticket.status == TicketStatus.review, 3),
    (Ticket.status == TicketStatus.blocked, 4),
    else_=5,
)

SORTABLE = {
    "key": Ticket.number,
    "number": Ticket.number,
    "title": Ticket.title,
    "type": Ticket.type,
    "priority": PRIORITY_ORDER,
    "status": STATUS_ORDER_CASE,
    "due_date": Ticket.due_date,
    "estimate_points": Ticket.estimate_points,
    "board_position": Ticket.board_position,
    "created_at": Ticket.created_at,
    "updated_at": Ticket.updated_at,
}


def _as_list(value: list[str] | None) -> list[str]:
    out: list[str] = []
    for item in value or []:
        out.extend(part.strip() for part in str(item).split(",") if part.strip())
    return out


def apply_sort(query: Query, sort: str | None) -> Query:
    """PRD §7.1: `?sort=field,-other` (leading dash = descending)."""
    specs = [s.strip() for s in (sort or "").split(",") if s.strip()]
    if not specs:
        return query.order_by(Ticket.board_position.asc(), Ticket.created_at.asc())
    for spec in specs:
        descending = spec.startswith("-")
        name = spec.lstrip("-")
        column = SORTABLE.get(name)
        if column is None:
            continue
        if name == "due_date":
            # AC-17.2: nulls always last
            query = query.order_by(
                Ticket.due_date.is_(None).asc() if not descending else Ticket.due_date.is_(None).desc()
            )
        query = query.order_by(column.desc() if descending else column.asc())
    return query.order_by(Ticket.created_at.asc(), Ticket.id.asc())


def ticket_query(
    db: Session,
    *,
    project_id: str | None = None,
    project_ids: list[str] | None = None,
    status: list[str] | None = None,
    type_: list[str] | None = None,
    priority: list[str] | None = None,
    assignee: list[str] | None = None,
    reporter: list[str] | None = None,
    label: list[str] | None = None,
    parent_id: str | None = None,
    roots_only: bool = False,
    q: str | None = None,
    due_before: date | None = None,
    updated_since: datetime | None = None,
    include_deleted: bool = False,
) -> Query:
    query = db.query(Ticket)
    if not include_deleted:
        query = query.filter(Ticket.deleted_at.is_(None))
    if project_id is not None:
        query = query.filter(Ticket.project_id == project_id)
    if project_ids is not None:
        query = query.filter(Ticket.project_id.in_(project_ids or ["-"]))

    statuses = _as_list(status)
    if statuses:
        query = query.filter(Ticket.status.in_([TicketStatus(s) for s in statuses]))
    types = _as_list(type_)
    if types:
        query = query.filter(Ticket.type.in_([TicketType(t) for t in types]))
    priorities = _as_list(priority)
    if priorities:
        query = query.filter(Ticket.priority.in_([TicketPriority(p) for p in priorities]))

    assignees = _as_list(assignee)
    if assignees:
        query = query.join(User, User.id == Ticket.assignee_id).filter(
            func.lower(User.username).in_([a.lower() for a in assignees])
        )
    if reporter:
        query = query.join(User, User.id == Ticket.reporter_id).filter(
            func.lower(User.username).in_([r.lower() for r in reporter])
        )
    for raw in label or []:
        names = [n.strip().lower() for n in raw.split(",") if n.strip()]
        if not names:
            continue
        query = (
            query.join(TicketLabel, TicketLabel.ticket_id == Ticket.id)
            .join(Label, Label.id == TicketLabel.label_id)
            .filter(func.lower(Label.name).in_(names))
        )
    if parent_id is not None:
        query = query.filter(Ticket.parent_id == parent_id)
    if roots_only:
        query = query.filter(Ticket.parent_id.is_(None))
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            or_(func.lower(Ticket.title).like(like), func.lower(Ticket.description_md).like(like))
        )
    if due_before is not None:
        query = query.filter(Ticket.due_date.isnot(None), Ticket.due_date <= due_before)
    if updated_since is not None:
        query = query.filter(Ticket.updated_at >= updated_since)
    return query


def visible_project_ids(db: Session, user_id: str, is_admin: bool) -> list[str] | None:
    if is_admin:
        return None
    return [
        pid
        for (pid,) in db.query(ProjectMember.project_id)
        .filter(ProjectMember.user_id == user_id)
        .all()
    ]


# --- search ---------------------------------------------------------------
DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")


def normalize_ar(text: str) -> str:
    """Lowercase + strip Arabic diacritics/tatweel + unify alef/ya/ta-marbuta."""
    text = unicodedata.normalize("NFKC", text)
    text = DIACRITICS.sub("", text)
    return (
        text.replace("أ", "ا")
        .replace("إ", "ا")
        .replace("آ", "ا")
        .replace("ى", "ي")
        .replace("ة", "ه")
        .lower()
    )


def search_tickets(
    db: Session, *, term: str, project_ids: list[str] | None, limit: int = 50
) -> list[Ticket]:
    """LIKE-based search with Arabic normalisation (v1; FTS5 is a later optimisation)."""
    normalized = normalize_ar(term)
    query = ticket_query(db, project_ids=project_ids)
    # SQLite lower() is ASCII-only, so normalise the Arabic side in Python for the
    # matched set (bounded by project scope) and filter there.
    candidates = query.order_by(Ticket.updated_at.desc()).limit(2000).all()
    hits = [t for t in candidates if normalized in normalize_ar(f"{t.title} {t.description_md}")]
    return hits[:limit]


def make_snippet(text: str, term: str, width: int = 140) -> str:
    """Return a plain-text snippet with the matched term wrapped in <em>."""
    flat = " ".join(text.split())
    if not flat:
        return ""
    normalized = normalize_ar(term)
    haystack = normalize_ar(flat)
    index = haystack.find(normalized)
    if index < 0:
        return flat[:width] + ("…" if len(flat) > width else "")
    start = max(0, index - width // 3)
    end = min(len(flat), index + len(term) + width // 2)
    excerpt = flat[start:end]
    highlighted = re.sub(
        re.escape(term), lambda m: f"<em>{m.group(0)}</em>", excerpt, flags=re.IGNORECASE
    )
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(flat) else ""
    return f"{prefix}{highlighted}{suffix}"
