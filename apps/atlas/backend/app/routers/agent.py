"""Agent API — machine access with a per-agent API key (PRD §7.9)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Query, Request, Response, status

from ..deps import (
    ApiKeyUser,
    DbDep,
    Pagination,
    ensure_member,
    ensure_project_writable,
    get_project,
    get_ticket,
)
from ..models import (
    Comment,
    Project,
    ProjectMember,
    Ticket,
    UserRole,
)
from ..schemas import (
    AgentMeOut,
    AgentTicketCreate,
    CommentCreate,
    CommentOut,
    TicketOut,
    TicketUpdate,
    TransitionRequest,
    TransitionResult,
)
from ..schemas import (
    ProjectRole as _Unused,  # noqa: F401 - keeps OpenAPI imports tidy
)
from ..services import events
from ..services.mentions import record_mentions
from ..services.serializers import comment_out, ticket_out_one, tickets_out, user_out
from ..services.tickets import create_ticket, transition_ticket, update_ticket

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/me", response_model=AgentMeOut)
def agent_me(db: DbDep, agent: ApiKeyUser) -> AgentMeOut:
    if agent.role in (UserRole.owner, UserRole.admin):
        projects = [{"key": p.key, "name": p.name} for p in db.query(Project).all()]
    else:
        projects = [
            {"key": m.project.key, "name": m.project.name}
            for m in db.query(ProjectMember).filter(ProjectMember.user_id == agent.id).all()
            if m.project is not None
        ]
    return AgentMeOut(user=user_out(agent), projects=projects)


@router.post(
    "/tickets",
    response_model=TicketOut,
    status_code=status.HTTP_201_CREATED,
    responses={200: {"description": "idempotent replay of client_ref"}},
)
def agent_create_ticket(
    payload: AgentTicketCreate,
    db: DbDep,
    agent: ApiKeyUser,
    request: Request,
    response: Response,
    background: BackgroundTasks,
) -> TicketOut:
    project = get_project(db, payload.project_key)
    ensure_project_writable(db, project, agent)
    ticket, created = create_ticket(
        db,
        project=project,
        actor=agent,
        payload=payload,
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    db.refresh(ticket)
    if not created:
        response.status_code = status.HTTP_200_OK
    else:
        events.dispatch(
            db,
            "ticket.created",
            {
                **events.event_payload(ticket, agent, getattr(request.state, "request_id", None)),
                "via": "agent_api",
            },
            project.id,
            background,
        )
    return ticket_out_one(db, ticket)


@router.get("/tickets/{ref}", response_model=TicketOut)
def agent_get_ticket(ref: str, db: DbDep, agent: ApiKeyUser) -> TicketOut:
    ticket = get_ticket(db, ref)
    ensure_member(db, ticket.project, agent)
    return ticket_out_one(db, ticket)


@router.patch("/tickets/{ref}", response_model=TicketOut)
def agent_update_ticket(
    ref: str,
    payload: TicketUpdate,
    db: DbDep,
    agent: ApiKeyUser,
    request: Request,
    background: BackgroundTasks,
) -> TicketOut:
    ticket = get_ticket(db, ref)
    ensure_project_writable(db, ticket.project, agent)
    data = payload.model_dump(exclude_unset=True)
    changes = update_ticket(
        db,
        ticket=ticket,
        actor=agent,
        payload=TicketUpdate(**data),
        request_id=getattr(request.state, "request_id", None),
        expected_version=payload.version,
    )
    db.commit()
    db.refresh(ticket)
    if changes:
        events.dispatch(
            db,
            "ticket.updated",
            {
                **events.event_payload(ticket, agent, getattr(request.state, "request_id", None)),
                "via": "agent_api",
                "changes": changes,
            },
            ticket.project_id,
            background,
        )
    return ticket_out_one(db, ticket)


@router.post("/tickets/{ref}/transition", response_model=TransitionResult)
def agent_transition(
    ref: str,
    payload: TransitionRequest,
    db: DbDep,
    agent: ApiKeyUser,
    request: Request,
    background: BackgroundTasks,
) -> TransitionResult:
    ticket = get_ticket(db, ref)
    role = ensure_project_writable(db, ticket.project, agent)
    ticket, warnings = transition_ticket(
        db,
        ticket=ticket,
        actor=agent,
        to=payload.to,
        role=role,
        blocked_reason=payload.blocked_reason,
        position=payload.position,
        expected_version=payload.version,
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    db.refresh(ticket)
    events.dispatch(
        db,
        "ticket.status_changed",
        {
            **events.event_payload(ticket, agent, getattr(request.state, "request_id", None)),
            "via": "agent_api",
            "to": payload.to.value,
        },
        ticket.project_id,
        background,
    )
    return TransitionResult(ticket=ticket_out_one(db, ticket), warnings=warnings)


@router.post(
    "/tickets/{ref}/comments", response_model=CommentOut, status_code=status.HTTP_201_CREATED
)
def agent_comment(
    ref: str, payload: CommentCreate, db: DbDep, agent: ApiKeyUser, request: Request
) -> CommentOut:
    ticket = get_ticket(db, ref)
    ensure_project_writable(db, ticket.project, agent)
    body = payload.body_md.strip()
    comment = Comment(ticket_id=ticket.id, author_id=agent.id, body_md=body)
    db.add(comment)
    db.flush()
    events.log_activity(
        db,
        project_id=ticket.project_id,
        ticket_id=ticket.id,
        actor_id=agent.id,
        action="comment",
        field="comment_id",
        new=comment.id,
        request_id=getattr(request.state, "request_id", None),
    )
    record_mentions(db, ticket=ticket, actor=agent, text=body, comment=comment)
    db.commit()
    db.refresh(comment)
    return comment_out(db, comment, ticket.key)


@router.get("/my-tickets", response_model=list[TicketOut])
def agent_my_tickets(
    db: DbDep,
    agent: ApiKeyUser,
    page: Pagination,
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[TicketOut]:
    from ..services.queries import ticket_query

    limit, offset = page
    query = ticket_query(
        db,
        assignee=[agent.username],
        status=[status_filter] if status_filter else None,
    )
    rows = query.order_by(Ticket.updated_at.desc()).offset(offset).limit(limit).all()
    return tickets_out(db, rows)
