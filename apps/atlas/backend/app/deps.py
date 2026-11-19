"""Auth, permission and lookup dependencies shared by all routers (PRD §3.1)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func
from sqlalchemy.orm import Session

from .database import get_db
from .errors import APIError, forbidden, not_found, unauthorised
from .models import (
    ApiKey,
    Project,
    ProjectMember,
    ProjectRole,
    Ticket,
    User,
    UserRole,
    utcnow,
)
from .security import decode_access_token, hash_api_key

bearer = HTTPBearer(auto_error=False, description="JWT from POST /api/auth/login")
DbDep = Annotated[Session, Depends(get_db)]


def get_current_user(
    db: DbDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> User:
    if creds is None or not creds.credentials:
        raise unauthorised("INVALID_TOKEN", "missing bearer token")
    try:
        payload = decode_access_token(creds.credentials)
        user_id = str(payload["sub"])
    except Exception:  # noqa: BLE001 - any JWT problem is a 401
        raise unauthorised("INVALID_TOKEN", "invalid or expired token") from None
    user = db.get(User, user_id)
    if user is None:
        raise unauthorised("INVALID_TOKEN", "token subject no longer exists")
    if not user.is_active:
        # AC-1.3 / §3.1: disabling an account kills its live tokens immediately
        raise APIError(401, "ACCOUNT_DISABLED", "account is disabled")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_api_key_user(
    db: DbDep,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> User:
    if not x_api_key:
        raise unauthorised("INVALID_API_KEY", "missing X-API-Key header")
    row = (
        db.query(ApiKey)
        .filter(ApiKey.key_hash == hash_api_key(x_api_key), ApiKey.revoked_at.is_(None))
        .first()
    )
    if row is None:
        raise unauthorised("INVALID_API_KEY", "invalid API key")
    user = db.get(User, row.user_id)
    if user is None or not user.is_active:
        raise unauthorised("INVALID_API_KEY", "API key owner is inactive")
    row.last_used_at = utcnow()
    db.commit()
    return user


ApiKeyUser = Annotated[User, Depends(get_api_key_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role not in (UserRole.owner, UserRole.admin):
        raise forbidden("FORBIDDEN", "requires admin role")
    return user


def require_owner(user: CurrentUser) -> User:
    if user.role != UserRole.owner:
        raise forbidden("FORBIDDEN", "requires owner role")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
OwnerUser = Annotated[User, Depends(require_owner)]


# --- project / ticket lookup ----------------------------------------------
def get_project(db: DbDep, ref: str) -> Project:
    """Accepts the project KEY (case-sensitive, uppercase) or its UUID."""
    project = db.query(Project).filter(Project.key == ref.upper()).first() if len(ref) <= 6 else None
    if project is None:
        project = db.get(Project, ref)
    if project is None:
        raise not_found("PROJECT_NOT_FOUND", "project not found")
    return project


ProjectByRef = Annotated[Project, Depends(get_project)]


def get_ticket(db: DbDep, ref: str) -> Ticket:
    """Accepts ATL-12, the ticket UUID, or a bare number (with ?project=)."""
    ticket: Ticket | None = None
    if "-" in ref:
        project_key, _, number = ref.rpartition("-")
        if number.isdigit():
            project = db.query(Project).filter(Project.key == project_key.upper()).first()
            if project is not None:
                ticket = (
                    db.query(Ticket)
                    .filter(
                        Ticket.project_id == project.id,
                        Ticket.number == int(number),
                        Ticket.deleted_at.is_(None),
                    )
                    .first()
                )
    if ticket is None:
        ticket = db.get(Ticket, ref)
    if ticket is None or ticket.deleted_at is not None:
        raise not_found("TICKET_NOT_FOUND", "ticket not found")
    return ticket


TicketByRef = Annotated[Ticket, Depends(get_ticket)]


def membership(db: Session, project_id: str, user_id: str) -> ProjectMember | None:
    return db.get(ProjectMember, {"project_id": project_id, "user_id": user_id})


def effective_role(db: Session, project: Project, user: User) -> ProjectRole | None:
    """Global owner/admin always act as project leads."""
    if user.role in (UserRole.owner, UserRole.admin):
        return ProjectRole.lead
    row = membership(db, project.id, user.id)
    return row.role_in_project if row else None


def ensure_member(db: Session, project: Project, user: User) -> ProjectRole:
    """AC-02.4: a non-member gets 404 so project existence never leaks."""
    role = effective_role(db, project, user)
    if role is None:
        raise not_found("PROJECT_NOT_FOUND", "project not found")
    return role


def ensure_active(project: Project) -> None:
    """AC-07.2: archived projects are not readable through board/ticket routes."""
    if project.archived_at is not None:
        raise not_found("PROJECT_ARCHIVED", "project is archived")


def ensure_project_lead(db: Session, project: Project, user: User) -> ProjectRole:
    """Lead check that still works on archived projects (needed to unarchive)."""
    role = ensure_member(db, project, user)
    if role != ProjectRole.lead:
        raise forbidden("FORBIDDEN", "requires project lead rights")
    return role


def ensure_project_writable(db: Session, project: Project, user: User) -> ProjectRole:
    role = ensure_member(db, project, user)
    ensure_active(project)
    return role


def ticket_visible(db: Session, ticket: Ticket, user: User) -> ProjectRole:
    return ensure_member(db, ticket.project, user)


def pagination(
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> tuple[int, int]:
    return limit, offset


Pagination = Annotated[tuple[int, int], Depends(pagination)]


def request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def lower(value: str):
    return func.lower(value)
