"""ORM → schema serialisation (batched, no per-row queries)."""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import (
    STATUS_LABELS,
    STATUS_ORDER,
    Activity,
    Attachment,
    Comment,
    Label,
    Mention,
    Notification,
    Project,
    ProjectMember,
    ProjectRole,
    Ticket,
    TicketLabel,
    TicketStatus,
    User,
)
from ..schemas import (
    ActivityOut,
    AttachmentOut,
    BoardColumn,
    BoardOut,
    CommentOut,
    LabelOut,
    MemberOut,
    NotificationOut,
    ProjectDetail,
    ProjectOut,
    TicketLite,
    TicketOut,
    UserBrief,
    UserOut,
)


def user_brief(user: User | None) -> UserBrief | None:
    if user is None:
        return None
    return UserBrief(
        id=user.id,
        username=user.username,
        name=user.name,
        avatar_url=user.avatar_url,
        color=user.color,
    )


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        name=user.name,
        avatar_url=user.avatar_url,
        color=user.color,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


def label_out(label: Label, ticket_count: int = 0) -> LabelOut:
    return LabelOut(
        id=label.id,
        name=label.name,
        color=label.color,
        project_id=label.project_id,
        ticket_count=ticket_count,
    )


def project_stats(db: Session, project_ids: list[str]) -> tuple[dict, dict, dict]:
    tickets: dict[str, int] = defaultdict(int)
    opens: dict[str, int] = defaultdict(int)
    members: dict[str, int] = defaultdict(int)
    if not project_ids:
        return tickets, opens, members
    for pid, count in (
        db.query(Ticket.project_id, func.count(Ticket.id))
        .filter(Ticket.project_id.in_(project_ids), Ticket.deleted_at.is_(None))
        .group_by(Ticket.project_id)
        .all()
    ):
        tickets[pid] = count
    for pid, count in (
        db.query(Ticket.project_id, func.count(Ticket.id))
        .filter(
            Ticket.project_id.in_(project_ids),
            Ticket.deleted_at.is_(None),
            Ticket.status != TicketStatus.done,
        )
        .group_by(Ticket.project_id)
        .all()
    ):
        opens[pid] = count
    for pid, count in (
        db.query(ProjectMember.project_id, func.count(ProjectMember.user_id))
        .filter(ProjectMember.project_id.in_(project_ids))
        .group_by(ProjectMember.project_id)
        .all()
    ):
        members[pid] = count
    return tickets, opens, members


def project_out(
    project: Project,
    *,
    my_role: ProjectRole | None = None,
    ticket_count: int = 0,
    open_count: int = 0,
    members_count: int = 0,
) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        key=project.key,
        name=project.name,
        description=project.description,
        color=project.color,
        ticket_count=ticket_count,
        open_count=open_count,
        members_count=members_count,
        archived_at=project.archived_at,
        created_at=project.created_at,
        updated_at=project.updated_at,
        my_role=my_role,
    )


def project_detail(
    db: Session, project: Project, my_role: ProjectRole | None = None
) -> ProjectDetail:
    tickets, opens, members = project_stats(db, [project.id])
    base = project_out(
        project,
        my_role=my_role,
        ticket_count=tickets[project.id],
        open_count=opens[project.id],
        members_count=members[project.id],
    )
    rows = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project.id)
        .order_by(ProjectMember.added_at)
        .all()
    )
    label_counts = dict(
        db.query(TicketLabel.label_id, func.count(TicketLabel.ticket_id))
        .filter(TicketLabel.ticket_id.in_(
            [
                tid
                for (tid,) in db.query(Ticket.id).filter(
                    Ticket.project_id == project.id, Ticket.deleted_at.is_(None)
                )
            ]
            or ["-"]
        ))
        .group_by(TicketLabel.label_id)
        .all()
    )
    labels = sorted(project.labels, key=lambda lb: lb.name)
    return ProjectDetail(
        **base.model_dump(),
        members=[
            MemberOut(
                user=user_brief(row.user),
                role_in_project=row.role_in_project,
                added_at=row.added_at,
            )
            for row in rows
            if row.user is not None
        ],
        labels=[label_out(lb, label_counts.get(lb.id, 0)) for lb in labels],
    )


# --- tickets ---------------------------------------------------------------
def _ticket_counts(db: Session, ticket_ids: list[str]) -> tuple[dict, dict]:
    children: dict[str, int] = defaultdict(int)
    comments: dict[str, int] = defaultdict(int)
    if not ticket_ids:
        return children, comments
    for pid, count in (
        db.query(Ticket.parent_id, func.count(Ticket.id))
        .filter(Ticket.parent_id.in_(ticket_ids), Ticket.deleted_at.is_(None))
        .group_by(Ticket.parent_id)
        .all()
    ):
        children[pid] = count
    for tid, count in (
        db.query(Comment.ticket_id, func.count(Comment.id))
        .filter(Comment.ticket_id.in_(ticket_ids))
        .group_by(Comment.ticket_id)
        .all()
    ):
        comments[tid] = count
    return children, comments


def _labels_by_ticket(db: Session, ticket_ids: list[str]) -> dict[str, list[Label]]:
    out: dict[str, list[Label]] = defaultdict(list)
    if not ticket_ids:
        return out
    rows = (
        db.query(TicketLabel.ticket_id, Label)
        .join(Label, Label.id == TicketLabel.label_id)
        .filter(TicketLabel.ticket_id.in_(ticket_ids))
        .order_by(Label.name)
        .all()
    )
    for tid, label in rows:
        out[tid].append(label)
    return out


def is_overdue(ticket: Ticket) -> bool:
    return bool(
        ticket.due_date and ticket.status != TicketStatus.done and ticket.due_date < date.today()
    )


def ticket_out(
    ticket: Ticket,
    *,
    children_count: int = 0,
    comment_count: int = 0,
    labels: list[Label] | None = None,
    attachments: list[Attachment] | None = None,
) -> TicketOut:
    return TicketOut(
        id=ticket.id,
        key=ticket.key,
        number=ticket.number,
        project_id=ticket.project_id,
        project_key=ticket.project.key,
        title=ticket.title,
        description_md=ticket.description_md,
        type=ticket.type,
        priority=ticket.priority,
        status=ticket.status,
        blocked_reason=ticket.blocked_reason,
        assignee=user_brief(ticket.assignee),
        reporter=user_brief(ticket.reporter),
        labels=[label_out(lb) for lb in (labels or [])],
        due_date=ticket.due_date,
        estimate_points=ticket.estimate_points,
        parent_id=ticket.parent_id,
        parent_key=ticket.parent.key if ticket.parent is not None else None,
        children_count=children_count,
        comment_count=comment_count,
        attachments=[AttachmentOut.model_validate(a, from_attributes=True) for a in (attachments or [])],
        board_position=ticket.board_position,
        version=ticket.version,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        closed_at=ticket.closed_at,
        is_overdue=is_overdue(ticket),
    )


def tickets_out(db: Session, tickets: list[Ticket]) -> list[TicketOut]:
    ids = [t.id for t in tickets]
    children, comments = _ticket_counts(db, ids)
    labels = _labels_by_ticket(db, ids)
    attachments: dict[str, list[Attachment]] = defaultdict(list)
    if ids:
        for row in (
            db.query(Attachment).filter(Attachment.ticket_id.in_(ids)).order_by(Attachment.created_at)
        ):
            attachments[row.ticket_id].append(row)
    return [
        ticket_out(
            t,
            children_count=children.get(t.id, 0),
            comment_count=comments.get(t.id, 0),
            labels=labels.get(t.id, []),
            attachments=attachments.get(t.id, []),
        )
        for t in tickets
    ]


def ticket_out_one(db: Session, ticket: Ticket) -> TicketOut:
    return tickets_out(db, [ticket])[0]


def ticket_lite(ticket: Ticket, *, children_count: int = 0, comment_count: int = 0, labels=None) -> TicketLite:
    return TicketLite(
        id=ticket.id,
        key=ticket.key,
        number=ticket.number,
        project_key=ticket.project.key,
        title=ticket.title,
        type=ticket.type,
        priority=ticket.priority,
        status=ticket.status,
        assignee=user_brief(ticket.assignee),
        labels=[label_out(lb) for lb in (labels or [])],
        due_date=ticket.due_date,
        board_position=ticket.board_position,
        children_count=children_count,
        comment_count=comment_count,
        is_overdue=is_overdue(ticket),
    )


def tickets_lite(db: Session, tickets: list[Ticket]) -> list[TicketLite]:
    ids = [t.id for t in tickets]
    children, comments = _ticket_counts(db, ids)
    labels = _labels_by_ticket(db, ids)
    return [
        ticket_lite(
            t,
            children_count=children.get(t.id, 0),
            comment_count=comments.get(t.id, 0),
            labels=labels.get(t.id, []),
        )
        for t in tickets
    ]


def board_out(
    db: Session, project: Project, *, my_role: ProjectRole | None, tickets: list[Ticket], done_limit: int = 50
) -> BoardOut:
    serialized = {t.id: item for t, item in zip(tickets, tickets_lite(db, tickets), strict=True)}
    columns: list[BoardColumn] = []
    for status in STATUS_ORDER:
        items = [
            serialized[t.id]
            for t in tickets
            if t.status == status
        ]
        items.sort(key=lambda i: (i.board_position, i.key))
        total = len(items)
        columns.append(
            BoardColumn(
                status=status,
                title=STATUS_LABELS[status],
                count=total,
                items=items[:done_limit] if status == TicketStatus.done else items,
                has_more=status == TicketStatus.done and total > done_limit,
            )
        )
    stats = project_stats(db, [project.id])
    return BoardOut(
        project=project_out(
            project,
            my_role=my_role,
            ticket_count=stats[0][project.id],
            open_count=stats[1][project.id],
            members_count=stats[2][project.id],
        ),
        columns=columns,
        generated_at=__import__("app.models", fromlist=["utcnow"]).utcnow(),
    )


# --- comments / activity / notifications -----------------------------------
def comment_out(db: Session, comment: Comment, ticket_key: str) -> CommentOut:
    mentioned = (
        db.query(User)
        .join(Mention, Mention.mentioned_user_id == User.id)
        .filter(Mention.comment_id == comment.id)
        .all()
    )
    return CommentOut(
        id=comment.id,
        ticket_id=comment.ticket_id,
        ticket_key=ticket_key,
        body_md=comment.body_md,
        author=user_brief(comment.author),
        mentions=[user_brief(u) for u in mentioned],
        edited_at=comment.edited_at,
        created_at=comment.created_at,
    )


def activity_out(row: Activity) -> ActivityOut:
    return ActivityOut(
        id=row.id,
        action=row.action,
        field=row.field,
        old_value=row.old_value,
        new_value=row.new_value,
        actor=user_brief(row.actor),
        ticket_id=row.ticket_id,
        ticket_key=row.ticket.key if row.ticket is not None else None,
        request_id=row.request_id,
        created_at=row.created_at,
    )


def notification_out(note: Notification) -> NotificationOut:
    return NotificationOut(
        id=note.id,
        type=note.type,
        payload=note.payload or {},
        actor=user_brief(note.actor),
        ticket_id=note.ticket_id,
        ticket_key=note.ticket.key if note.ticket is not None else None,
        read_at=note.read_at,
        created_at=note.created_at,
    )
