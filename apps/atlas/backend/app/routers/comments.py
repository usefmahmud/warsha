"""Comments (with @mentions) — PRD §7.6."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Request, status

from ..deps import (
    CurrentUser,
    DbDep,
    Pagination,
    ProjectRole,
    TicketByRef,
    ensure_member,
    ensure_project_writable,
)
from ..errors import forbidden, not_found
from ..models import Comment, Mention, UserRole, utcnow
from ..schemas import CommentCreate, CommentOut, CommentUpdate, Page
from ..services import events
from ..services.mentions import record_mentions
from ..services.serializers import comment_out

router = APIRouter(tags=["comments"])


@router.get("/tickets/{ref}/comments", response_model=Page[CommentOut])
def list_comments(ticket: TicketByRef, db: DbDep, user: CurrentUser, page: Pagination):
    ensure_member(db, ticket.project, user)
    limit, offset = page
    query = db.query(Comment).filter(Comment.ticket_id == ticket.id)
    total = query.count()
    rows = (
        query.order_by(Comment.created_at.asc(), Comment.id.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return Page[CommentOut](
        items=[comment_out(db, c, ticket.key) for c in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/tickets/{ref}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
def add_comment(
    ticket: TicketByRef,
    payload: CommentCreate,
    db: DbDep,
    user: CurrentUser,
    request: Request,
    background: BackgroundTasks,
) -> CommentOut:
    ensure_project_writable(db, ticket.project, user)
    body = payload.body_md.strip()
    comment = Comment(ticket_id=ticket.id, author_id=user.id, body_md=body)
    db.add(comment)
    db.flush()

    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="comment",
        field="comment_id",
        new=comment.id,
        request_id=getattr(request.state, "request_id", None),
    )
    mentioned = record_mentions(db, ticket=ticket, actor=user, text=body, comment=comment)
    ticket.updated_at = utcnow()
    db.add(ticket)
    db.commit()
    db.refresh(comment)
    events.dispatch(
        db,
        "comment.created",
        {
            **events.event_payload(ticket, user, getattr(request.state, "request_id", None)),
            "comment": {"id": comment.id, "snippet": body[:200]},
            "mentions": [u.username for u in mentioned],
        },
        ticket.project_id,
        background,
    )
    return comment_out(db, comment, ticket.key)


def _get_comment(db, comment_id: str) -> Comment:
    comment = db.get(Comment, comment_id)
    if comment is None:
        raise not_found("NOT_FOUND", "comment not found")
    return comment


@router.patch("/comments/{comment_id}", response_model=CommentOut)
def edit_comment(
    comment_id: str, payload: CommentUpdate, db: DbDep, user: CurrentUser
) -> CommentOut:
    comment = _get_comment(db, comment_id)
    ticket = comment.ticket
    role = ensure_member(db, ticket.project, user)
    is_lead = role == ProjectRole.lead or user.role in (UserRole.owner, UserRole.admin)
    if comment.author_id != user.id and not is_lead:
        raise forbidden("FORBIDDEN", "you can only edit your own comments")
    comment.body_md = payload.body_md.strip()
    comment.edited_at = utcnow()
    db.add(comment)
    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="comment_edited",
        field="comment_id",
        new=comment.id,
    )
    record_mentions(db, ticket=ticket, actor=user, text=comment.body_md, comment=comment)
    db.commit()
    db.refresh(comment)
    return comment_out(db, comment, ticket.key)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: str, db: DbDep, user: CurrentUser) -> None:
    comment = _get_comment(db, comment_id)
    ticket = comment.ticket
    role = ensure_member(db, ticket.project, user)
    is_lead = role == ProjectRole.lead or user.role in (UserRole.owner, UserRole.admin)
    if comment.author_id != user.id and not is_lead:
        raise forbidden("FORBIDDEN", "you can only delete your own comments")
    # AC-12.6: soft delete keeps the row and the thread readable
    comment.body_md = "[deleted]"
    comment.edited_at = utcnow()
    db.add(comment)
    db.query(Mention).filter(Mention.comment_id == comment.id).delete(synchronize_session=False)
    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="comment_deleted",
        field="comment_id",
        old=comment.id,
    )
    db.commit()
