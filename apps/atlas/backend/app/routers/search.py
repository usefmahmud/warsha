"""Global search (PRD §7.7 / AC-19.x)."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..deps import CurrentUser, DbDep, ensure_member, get_project
from ..errors import invalid
from ..models import UserRole
from ..schemas import SearchHit, SearchOut
from ..services.queries import make_snippet, search_tickets, visible_project_ids
from ..services.serializers import tickets_lite

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchOut)
def search(
    db: DbDep,
    user: CurrentUser,
    q: str = Query(min_length=1, max_length=120),
    project: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
) -> SearchOut:
    if len(q.strip()) < 2:
        raise invalid("QUERY_TOO_SHORT", "search terms must be at least 2 characters")
    project_ids = visible_project_ids(db, user.id, user.role in (UserRole.owner, UserRole.admin))
    if project:
        row = get_project(db, project)
        ensure_member(db, row, user)
        project_ids = [row.id]

    tickets = search_tickets(db, term=q.strip(), project_ids=project_ids, limit=limit)
    lite = tickets_lite(db, tickets)
    hits = [
        SearchHit(
            ticket=item,
            snippet=make_snippet(f"{ticket.title} {ticket.description_md}", q.strip()),
            rank=float(len(tickets) - index),
        )
        for index, (ticket, item) in enumerate(zip(tickets, lite, strict=True))
    ]
    return SearchOut(items=hits, total=len(hits))
