"""Notifications and My Work (PRD §7.7, §7.8)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, status
from sqlalchemy import func

from ..deps import CurrentUser, DbDep, Pagination
from ..errors import not_found
from ..models import Mention, Notification, Ticket, TicketStatus, utcnow
from ..schemas import (
    MyWorkMentions,
    MyWorkOut,
    NotificationOut,
    NotificationPage,
    Page,
    UnreadCount,
)
from ..services.mentions import snippet
from ..services.queries import ticket_query
from ..services.serializers import notification_out, tickets_lite

router = APIRouter(tags=["notifications"])

OPEN = [
    TicketStatus.backlog,
    TicketStatus.todo,
    TicketStatus.in_progress,
    TicketStatus.review,
    TicketStatus.blocked,
]


@router.get("/notifications", response_model=NotificationPage)
def list_notifications(
    db: DbDep,
    user: CurrentUser,
    page: Pagination,
    unread: bool | None = None,
    type_filter: str | None = None,
) -> NotificationPage:
    limit, offset = page
    query = db.query(Notification).filter(Notification.user_id == user.id)
    if unread:
        query = query.filter(Notification.read_at.is_(None))
    if type_filter:
        query = query.filter(Notification.type == type_filter)
    total = query.count()
    unread_count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .scalar()
        or 0
    )
    rows = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return NotificationPage(
        items=[notification_out(n) for n in rows],
        total=total,
        limit=limit,
        offset=offset,
        unread_count=unread_count,
    )


@router.get("/notifications/unread_count", response_model=UnreadCount)
def unread_count(db: DbDep, user: CurrentUser) -> UnreadCount:
    count = (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .scalar()
        or 0
    )
    return UnreadCount(count=count)


@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(notification_id: str, db: DbDep, user: CurrentUser) -> None:
    note = db.get(Notification, notification_id)
    if note is None or note.user_id != user.id:
        raise not_found("NOT_FOUND", "notification not found")
    if note.read_at is None:
        note.read_at = utcnow()
        db.add(note)
        db.commit()


@router.post("/notifications/read-all", status_code=status.HTTP_200_OK)
def mark_all_read(db: DbDep, user: CurrentUser) -> dict:
    updated = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: utcnow()}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}


# --- My Work ---------------------------------------------------------------
@router.get("/me/work", response_model=MyWorkOut)
def my_work(db: DbDep, user: CurrentUser, limit: int = 50) -> MyWorkOut:
    limit = max(1, min(limit, 200))
    today = date.today()
    horizon = today + timedelta(days=3)

    open_rows = (
        ticket_query(db, assignee=[user.username], status=[s.value for s in OPEN])
        .order_by(Ticket.due_date.is_(None), Ticket.due_date, Ticket.board_position)
        .limit(limit)
        .all()
    )
    overdue_rows = [t for t in open_rows if t.due_date and t.due_date < today]
    due_soon_rows = [
        t for t in open_rows if t.due_date and today <= t.due_date <= horizon
    ]
    assigned_rows = [t for t in open_rows if t.status != TicketStatus.done]

    closed_rows = (
        ticket_query(db, assignee=[user.username], status=[TicketStatus.done.value])
        .filter(Ticket.closed_at.isnot(None), Ticket.closed_at >= utcnow() - timedelta(days=7))
        .order_by(Ticket.closed_at.desc())
        .limit(20)
        .all()
    )

    mentions: list[MyWorkMentions] = []
    mention_rows = (
        db.query(Mention, Notification)
        .join(
            Notification,
            (Notification.ticket_id == Mention.ticket_id)
            & (Notification.user_id == Mention.mentioned_user_id)
            & (Notification.type == "mention"),
        )
        .filter(Mention.mentioned_user_id == user.id, Notification.read_at.is_(None))
        .order_by(Mention.created_at.desc())
        .limit(20)
        .all()
    )
    tickets_by_id = {}
    for mention, note in mention_rows:
        ticket = mention.ticket_id and db.get(Ticket, mention.ticket_id)
        if ticket is None or ticket.deleted_at is not None:
            continue
        tickets_by_id[ticket.id] = ticket
        mentions.append(
            MyWorkMentions(
                notification_id=note.id,
                ticket=tickets_lite(db, [ticket])[0],
                comment_id=mention.comment_id,
                snippet=snippet((note.payload or {}).get("snippet", ""), 120),
                unread=True,
                created_at=mention.created_at,
            )
        )

    return MyWorkOut(
        assigned=tickets_lite(db, assigned_rows),
        due_soon=tickets_lite(db, due_soon_rows),
        overdue=tickets_lite(db, overdue_rows),
        closed_recent=tickets_lite(db, closed_rows),
        mentions=mentions,
    )


@router.get("/me/mentions", response_model=Page[NotificationOut])
def my_mentions(
    db: DbDep, user: CurrentUser, page: Pagination, unread: bool = False
) -> Page[NotificationOut]:
    limit, offset = page
    query = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.type == "mention"
    )
    if unread:
        query = query.filter(Notification.read_at.is_(None))
    total = query.count()
    rows = query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()
    return Page[NotificationOut](
        items=[notification_out(n) for n in rows], total=total, limit=limit, offset=offset
    )
