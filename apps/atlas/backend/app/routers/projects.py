"""Projects: CRUD, archive, members, board and project ticket list (PRD §7.4)."""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Query, Request, status
from sqlalchemy import func

from ..deps import (
    AdminUser,
    CurrentUser,
    DbDep,
    Pagination,
    ProjectByRef,
    effective_role,
    ensure_active,
    ensure_member,
    ensure_project_lead,
    ensure_project_writable,
    membership,
)
from ..errors import bad_request, conflict, not_found
from ..models import (
    Project,
    ProjectMember,
    ProjectRole,
    Ticket,
    User,
    UserRole,
    utcnow,
)
from ..schemas import (
    BoardOut,
    MemberAdd,
    Page,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ProjectUpdate,
    TicketCreate,
    TicketOut,
)
from ..services import events
from ..services.queries import apply_sort, ticket_query
from ..services.serializers import (
    board_out,
    project_detail,
    project_out,
    project_stats,
    ticket_out_one,
    tickets_out,
)
from ..services.tickets import create_ticket

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=Page[ProjectOut])
def list_projects(
    db: DbDep,
    user: CurrentUser,
    page: Pagination,
    include_archived: bool = False,
    q: str | None = Query(default=None, max_length=120),
) -> Page[ProjectOut]:
    limit, offset = page
    query = db.query(Project)
    if user.role not in (UserRole.owner, UserRole.admin):
        query = query.join(ProjectMember, ProjectMember.project_id == Project.id).filter(
            ProjectMember.user_id == user.id
        )
    if not include_archived:
        query = query.filter(Project.archived_at.is_(None))
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            func.lower(Project.name).like(like)
            | func.lower(Project.key).like(like)
            | func.lower(Project.description).like(like)
        )
    total = query.count()
    rows = query.order_by(Project.archived_at.isnot(None), Project.key).offset(offset).limit(limit).all()
    stats = project_stats(db, [p.id for p in rows])
    return Page[ProjectOut](
        items=[
            project_out(
                p,
                my_role=effective_role(db, p, user),
                ticket_count=stats[0][p.id],
                open_count=stats[1][p.id],
                members_count=stats[2][p.id],
            )
            for p in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: DbDep, admin: AdminUser) -> ProjectOut:
    if db.query(Project).filter(Project.key == payload.key).first():
        raise conflict("PROJECT_KEY_EXISTS", f"project key {payload.key} already exists")
    project = Project(
        key=payload.key,
        name=payload.name,
        description=payload.description or "",
        color=payload.color,
        created_by=admin.id,
    )
    db.add(project)
    db.flush()
    db.add(
        ProjectMember(project_id=project.id, user_id=admin.id, role_in_project=ProjectRole.lead)
    )
    for user_id in payload.member_ids or []:
        if user_id == admin.id:
            continue
        if db.get(User, user_id) is None:
            raise not_found("USER_NOT_FOUND", f"user {user_id} not found")
        if membership(db, project.id, user_id) is None:
            db.add(
                ProjectMember(
                    project_id=project.id, user_id=user_id, role_in_project=ProjectRole.member
                )
            )
    db.flush()
    events.log_activity(
        db,
        project_id=project.id,
        actor_id=admin.id,
        action="created",
        field="project",
        new=project.key,
    )
    db.commit()
    db.refresh(project)
    return project_out(
        project,
        my_role=ProjectRole.lead,
        ticket_count=0,
        open_count=0,
        members_count=1 + len(payload.member_ids or []),
    )


@router.get("/{ref}", response_model=ProjectDetail)
def get_project(project: ProjectByRef, db: DbDep, user: CurrentUser) -> ProjectDetail:
    role = ensure_member(db, project, user)
    return project_detail(db, project, my_role=role)


@router.patch("/{ref}", response_model=ProjectOut)
def update_project(
    project: ProjectByRef, payload: ProjectUpdate, db: DbDep, user: CurrentUser
) -> ProjectOut:
    role = ensure_project_lead(db, project, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(project, field, value)
    project.updated_at = utcnow()
    db.add(project)
    db.commit()
    stats = project_stats(db, [project.id])
    return project_out(
        project,
        my_role=role,
        ticket_count=stats[0][project.id],
        open_count=stats[1][project.id],
        members_count=stats[2][project.id],
    )


@router.post("/{ref}/archive", status_code=status.HTTP_204_NO_CONTENT)
def archive_project(project: ProjectByRef, db: DbDep, user: CurrentUser) -> None:
    ensure_project_lead(db, project, user)
    if project.archived_at is None:
        project.archived_at = utcnow()
        project.updated_at = utcnow()
        events.log_activity(
            db,
            project_id=project.id,
            actor_id=user.id,
            action="archived",
            field="archived_at",
            new=project.archived_at,
        )
        db.add(project)
        db.commit()


@router.post("/{ref}/unarchive", status_code=status.HTTP_204_NO_CONTENT)
def unarchive_project(project: ProjectByRef, db: DbDep, user: CurrentUser) -> None:
    ensure_project_lead(db, project, user)
    if project.archived_at is not None:
        project.archived_at = None
        project.updated_at = utcnow()
        events.log_activity(
            db,
            project_id=project.id,
            actor_id=user.id,
            action="unarchived",
            field="archived_at",
            old=None,
            new=None,
        )
        db.add(project)
        db.commit()


# --- members ---------------------------------------------------------------
@router.get("/{ref}/members", response_model=list[dict])
def list_members(project: ProjectByRef, db: DbDep, user: CurrentUser) -> list[dict]:
    ensure_member(db, project, user)
    from ..services.serializers import user_brief

    rows = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id)
        .order_by(ProjectMember.added_at)
        .all()
    )
    return [
        {
            "user": user_brief(m.user).model_dump() if m.user else None,
            "role_in_project": m.role_in_project.value,
            "added_at": m.added_at.isoformat(timespec="seconds"),
        }
        for m in rows
    ]


@router.post("/{ref}/members", status_code=status.HTTP_204_NO_CONTENT)
def add_member(
    project: ProjectByRef, payload: MemberAdd, db: DbDep, user: CurrentUser
) -> None:
    ensure_project_lead(db, project, user)
    target = db.get(User, payload.user_id)
    if target is None:
        raise not_found("USER_NOT_FOUND", "user not found")
    if membership(db, project.id, target.id) is not None:
        raise conflict("MEMBER_EXISTS", f"{target.username} is already a member")
    db.add(
        ProjectMember(
            project_id=project.id,
            user_id=target.id,
            role_in_project=payload.role_in_project,
        )
    )
    events.log_activity(
        db,
        project_id=project.id,
        actor_id=user.id,
        action="member_added",
        field="members",
        new=target.username,
    )
    events.notify(
        db,
        user_id=target.id,
        actor_id=user.id,
        type="project",
        payload={"project_key": project.key, "project_name": project.name},
    )
    db.commit()


@router.delete("/{ref}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(
    project: ProjectByRef, user_id: str, db: DbDep, user: CurrentUser
) -> None:
    ensure_project_lead(db, project, user)
    row = membership(db, project.id, user_id)
    if row is None:
        raise not_found("MEMBER_NOT_FOUND", "member not found")
    if project.created_by == user_id:
        raise bad_request("INVALID_REQUEST", "cannot remove the project creator")
    # AC-06.3: unassign their tickets, keep the tickets, leave an activity trail
    affected = (
        db.query(Ticket)
        .filter(
            Ticket.project_id == project.id,
            Ticket.assignee_id == user_id,
            Ticket.deleted_at.is_(None),
        )
        .all()
    )
    for ticket in affected:
        ticket.assignee_id = None
        ticket.version = (ticket.version or 1) + 1
        ticket.updated_at = utcnow()
        db.add(ticket)
        events.log_activity(
            db,
            project_id=project.id,
            ticket_id=ticket.id,
            actor_id=user.id,
            action="assignee_removed_by_membership",
            field="assignee_id",
            old=user_id,
            new=None,
        )
    db.delete(row)
    db.commit()


# --- board / tickets -------------------------------------------------------
@router.get("/{ref}/board", response_model=BoardOut)
def project_board(
    project: ProjectByRef,
    db: DbDep,
    user: CurrentUser,
    assignee: list[str] | None = Query(default=None),
    label: list[str] | None = Query(default=None),
    priority: list[str] | None = Query(default=None),
    q: str | None = None,
) -> BoardOut:
    role = ensure_member(db, project, user)
    ensure_active(project)
    query = ticket_query(
        db,
        project_id=project.id,
        assignee=assignee,
        label=label,
        priority=priority,
        q=q,
    )
    tickets = query.order_by(Ticket.board_position, Ticket.created_at).all()
    return board_out(db, project, my_role=role, tickets=tickets)


@router.get("/{ref}/tickets", response_model=Page[TicketOut])
def project_tickets(
    project: ProjectByRef,
    db: DbDep,
    user: CurrentUser,
    page: Pagination,
    status_filter: list[str] | None = Query(default=None, alias="status"),
    type_filter: list[str] | None = Query(default=None, alias="type"),
    priority: list[str] | None = Query(default=None),
    assignee: list[str] | None = Query(default=None),
    reporter: list[str] | None = Query(default=None),
    label: list[str] | None = Query(default=None),
    parent_id: str | None = None,
    q: str | None = None,
    due_before: str | None = None,
    updated_since: str | None = None,
    sort: str | None = None,
    roots_only: bool = False,
) -> Page[TicketOut]:
    ensure_project_writable(db, project, user)

    query = ticket_query(
        db,
        project_id=project.id,
        status=status_filter,
        type_=type_filter,
        priority=priority,
        assignee=assignee,
        reporter=reporter,
        label=label,
        parent_id=parent_id,
        q=q,
        roots_only=roots_only,
        due_before=_parse_date(due_before),
        updated_since=_parse_dt(updated_since),
    )
    limit, offset = page
    total = query.count()
    rows = apply_sort(query, sort).offset(offset).limit(limit).all()
    return Page[TicketOut](
        items=tickets_out(db, rows), total=total, limit=limit, offset=offset
    )


@router.post("/{ref}/tickets", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
def create_project_ticket(
    project: ProjectByRef,
    payload: TicketCreate,
    db: DbDep,
    user: CurrentUser,
    request: Request,
    background: BackgroundTasks,
):
    ensure_project_writable(db, project, user)
    ticket, created = create_ticket(
        db,
        project=project,
        actor=user,
        payload=payload,
        request_id=getattr(request.state, "request_id", None),
    )
    db.commit()
    db.refresh(ticket)
    if created:
        events.dispatch(
            db,
            "ticket.created",
            events.event_payload(ticket, user, getattr(request.state, "request_id", None)),
            project.id,
            background,
        )
    return ticket_out_one(db, ticket)


def _parse_date(value: str | None):
    from datetime import date as date_cls

    if not value:
        return None
    try:
        return date_cls.fromisoformat(value)
    except ValueError:
        raise bad_request("BAD_REQUEST", f"invalid date {value!r} (YYYY-MM-DD)") from None


def _parse_dt(value: str | None):
    from datetime import datetime as dt

    if not value:
        return None
    try:
        return dt.fromisoformat(value).replace(tzinfo=None)
    except ValueError:
        raise bad_request("BAD_REQUEST", f"invalid timestamp {value!r}") from None
