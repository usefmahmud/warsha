"""Ticket endpoints: get/patch/transition/children/activity/attachments/labels (PRD §7.5)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Header, Query, Request, status

from ..deps import (
    CurrentUser,
    DbDep,
    Pagination,
    TicketByRef,
    ensure_member,
    ensure_project_lead,
    ensure_project_writable,
    get_project,
)
from ..errors import APIError, bad_request, conflict, forbidden, invalid, not_found
from ..models import (
    Attachment,
    ProjectRole,
    Ticket,
    TicketLabel,
    TicketStatus,
    UserRole,
)
from ..schemas import (
    ActivityOut,
    AttachmentCreate,
    AttachmentOut,
    LabelLink,
    Page,
    TicketOut,
    TicketUpdate,
    TransitionRequest,
    TransitionResult,
)
from ..services import events
from ..services.queries import apply_sort, ticket_query, visible_project_ids
from ..services.serializers import activity_out, ticket_out_one, tickets_out
from ..services.tickets import (
    soft_delete,
    transition_ticket,
    update_ticket,
)

router = APIRouter(tags=["tickets"])


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _if_match(if_match: str | None) -> int | None:
    if not if_match:
        return None
    raw = if_match.strip().strip('"')
    if not raw.isdigit():
        raise invalid("VALIDATION_ERROR", "If-Match must be the ticket version number")
    return int(raw)


@router.get("/tickets", response_model=Page[TicketOut])
def list_tickets(
    db: DbDep,
    user: CurrentUser,
    page: Pagination,
    project: str | None = None,
    status_filter: list[str] | None = Query(default=None, alias="status"),
    type_filter: list[str] | None = Query(default=None, alias="type"),
    priority: list[str] | None = Query(default=None),
    assignee: list[str] | None = Query(default=None),
    label: list[str] | None = Query(default=None),
    q: str | None = None,
    updated_since: str | None = None,
    sort: str | None = None,
) -> Page[TicketOut]:
    """Cross-project list for polling and My Work (scoped to the caller's projects)."""
    project_id = None
    project_ids = visible_project_ids(db, user.id, user.role in (UserRole.owner, UserRole.admin))
    if project:
        row = get_project(db, project)
        ensure_member(db, row, user)
        project_id, project_ids = row.id, None
    since = None
    if updated_since:
        from datetime import datetime as dt

        try:
            since = dt.fromisoformat(updated_since).replace(tzinfo=None)
        except ValueError:
            raise bad_request("BAD_REQUEST", "invalid updated_since") from None
    query = ticket_query(
        db,
        project_id=project_id,
        project_ids=project_ids,
        status=status_filter,
        type_=type_filter,
        priority=priority,
        assignee=assignee,
        label=label,
        q=q,
        updated_since=since,
    )
    limit, offset = page
    total = query.count()
    rows = apply_sort(query, sort).offset(offset).limit(limit).all()
    return Page[TicketOut](items=tickets_out(db, rows), total=total, limit=limit, offset=offset)


@router.get("/tickets/{ref}", response_model=TicketOut)
def get_ticket_detail(ticket: TicketByRef, db: DbDep, user: CurrentUser) -> TicketOut:
    ensure_member(db, ticket.project, user)
    return ticket_out_one(db, ticket)


@router.patch("/tickets/{ref}", response_model=TicketOut)
def patch_ticket(
    ticket: TicketByRef,
    payload: TicketUpdate,
    db: DbDep,
    user: CurrentUser,
    request: Request,
    background: BackgroundTasks,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> TicketOut:
    ensure_project_writable(db, ticket.project, user)
    expected = _if_match(if_match)
    if expected is None:
        expected = payload.version
    changes = update_ticket(
        db,
        ticket=ticket,
        actor=user,
        payload=payload,
        request_id=_request_id(request),
        expected_version=expected,
    )
    db.commit()
    db.refresh(ticket)
    if changes:
        event = "ticket.updated"
        if any(c["field"] == "assignee_id" for c in changes):
            events.dispatch(
                db,
                "ticket.assigned",
                events.event_payload(ticket, user, _request_id(request)),
                ticket.project_id,
                background,
            )
        events.dispatch(
            db,
            event,
            events.event_payload(ticket, user, _request_id(request)),
            ticket.project_id,
            background,
        )
    return ticket_out_one(db, ticket)


@router.post("/tickets/{ref}/transition", response_model=TransitionResult)
def transition(
    ticket: TicketByRef,
    payload: TransitionRequest,
    db: DbDep,
    user: CurrentUser,
    request: Request,
    background: BackgroundTasks,
    if_match: str | None = Header(default=None, alias="If-Match"),
) -> TransitionResult:
    ensure_project_writable(db, ticket.project, user)
    expected = _if_match(if_match)
    if expected is None:
        expected = payload.version
    role = ensure_project_writable(db, ticket.project, user)
    ticket, warnings = transition_ticket(
        db,
        ticket=ticket,
        actor=user,
        to=payload.to,
        role=role,
        blocked_reason=payload.blocked_reason,
        position=payload.position,
        expected_version=expected,
        request_id=_request_id(request),
    )
    db.commit()
    db.refresh(ticket)
    events.dispatch(
        db,
        "ticket.status_changed",
        {**events.event_payload(ticket, user, _request_id(request)), "to": payload.to.value},
        ticket.project_id,
        background,
    )
    if payload.to == TicketStatus.done:
        events.dispatch(
            db,
            "ticket.done",
            events.event_payload(ticket, user, _request_id(request)),
            ticket.project_id,
            background,
        )
    return TransitionResult(ticket=ticket_out_one(db, ticket), warnings=warnings)


@router.delete("/tickets/{ref}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(
    ticket: TicketByRef, db: DbDep, user: CurrentUser, request: Request
) -> None:
    ensure_project_lead(db, ticket.project, user)
    soft_delete(db, ticket=ticket, actor=user, request_id=_request_id(request))
    db.commit()


@router.get("/tickets/{ref}/children", response_model=Page[TicketOut])
def list_children(
    ticket: TicketByRef, db: DbDep, user: CurrentUser, page: Pagination
) -> Page[TicketOut]:
    ensure_member(db, ticket.project, user)
    query = db.query(Ticket).filter(
        Ticket.parent_id == ticket.id, Ticket.deleted_at.is_(None)
    )
    limit, offset = page
    total = query.count()
    rows = query.order_by(Ticket.board_position, Ticket.created_at).offset(offset).limit(limit).all()
    return Page[TicketOut](items=tickets_out(db, rows), total=total, limit=limit, offset=offset)


@router.get("/tickets/{ref}/activity", response_model=Page[ActivityOut])
def ticket_activity(ticket: TicketByRef, db: DbDep, user: CurrentUser, page: Pagination):
    ensure_member(db, ticket.project, user)
    from ..models import Activity

    limit, offset = page
    query = db.query(Activity).filter(Activity.ticket_id == ticket.id)
    total = query.count()
    rows = (
        query.order_by(Activity.created_at.desc(), Activity.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return Page[ActivityOut](
        items=[activity_out(r) for r in rows], total=total, limit=limit, offset=offset
    )


# --- attachments (link only in v1) ----------------------------------------
@router.get("/tickets/{ref}/attachments", response_model=list[AttachmentOut])
def list_attachments(ticket: TicketByRef, db: DbDep, user: CurrentUser) -> list[AttachmentOut]:
    ensure_member(db, ticket.project, user)
    rows = (
        db.query(Attachment)
        .filter(Attachment.ticket_id == ticket.id)
        .order_by(Attachment.created_at)
        .all()
    )
    return [AttachmentOut.model_validate(r, from_attributes=True) for r in rows]


@router.post(
    "/tickets/{ref}/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED
)
def add_attachment(
    ticket: TicketByRef, payload: AttachmentCreate, db: DbDep, user: CurrentUser
) -> AttachmentOut:
    ensure_project_writable(db, ticket.project, user)
    if payload.kind != "link":
        raise APIError(400, "NOT_SUPPORTED_IN_V1", "file uploads are not supported in v1")
    if not payload.url.lower().startswith(("http://", "https://")):
        raise invalid("INVALID_URL", "attachment url must be http(s)")
    row = Attachment(
        ticket_id=ticket.id, kind="link", url=payload.url, title=payload.title, created_by=user.id
    )
    db.add(row)
    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="updated",
        field="attachments",
        new=payload.url,
    )
    db.commit()
    db.refresh(row)
    return AttachmentOut.model_validate(row, from_attributes=True)


@router.delete("/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: str, db: DbDep, user: CurrentUser) -> None:
    row = db.get(Attachment, attachment_id)
    if row is None:
        raise not_found("NOT_FOUND", "attachment not found")
    ticket = row.ticket
    role = ensure_member(db, ticket.project, user)
    if row.created_by != user.id and role != ProjectRole.lead and user.role not in (
        UserRole.owner,
        UserRole.admin,
    ):
        raise forbidden("FORBIDDEN", "you can only delete your own attachments")
    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="updated",
        field="attachments",
        old=row.url,
    )
    db.delete(row)
    db.commit()


# --- labels on a ticket ----------------------------------------------------
@router.post("/tickets/{ref}/labels", status_code=status.HTTP_204_NO_CONTENT)
def link_label(ticket: TicketByRef, payload: LabelLink, db: DbDep, user: CurrentUser) -> None:
    ensure_project_writable(db, ticket.project, user)
    from ..models import Label

    label = db.get(Label, payload.label_id)
    if label is None or label.project_id != ticket.project_id:
        raise not_found("LABEL_NOT_FOUND", "label not found")
    exists = db.get(TicketLabel, {"ticket_id": ticket.id, "label_id": label.id})
    if exists is not None:
        raise conflict("LABEL_ALREADY_LINKED", "label is already on this ticket")
    db.add(TicketLabel(ticket_id=ticket.id, label_id=label.id))
    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="updated",
        field="labels",
        new=label.name,
    )
    db.commit()


@router.delete("/tickets/{ref}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def unlink_label(ticket: TicketByRef, label_id: str, db: DbDep, user: CurrentUser) -> None:
    ensure_project_writable(db, ticket.project, user)
    link = db.get(TicketLabel, {"ticket_id": ticket.id, "label_id": label_id})
    if link is None:
        raise not_found("LABEL_NOT_FOUND", "label is not linked to this ticket")
    name = link.label.name if link.label is not None else None
    db.delete(link)
    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=user.id,
        action="updated",
        field="labels",
        old=name,
    )
    db.commit()
