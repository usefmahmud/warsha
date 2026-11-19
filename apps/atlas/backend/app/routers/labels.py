"""Project labels (PRD §7.6)."""

from __future__ import annotations

from fastapi import APIRouter, status
from sqlalchemy import func

from ..deps import CurrentUser, DbDep, ProjectByRef, ensure_member, ensure_project_lead
from ..errors import conflict, not_found
from ..models import Label, Ticket, TicketLabel
from ..schemas import LabelCreate, LabelOut, LabelUpdate
from ..services.serializers import label_out

router = APIRouter(tags=["labels"])


def _counts(db, project_id: str) -> dict[str, int]:
    return dict(
        db.query(TicketLabel.label_id, func.count(TicketLabel.ticket_id))
        .join(Ticket, Ticket.id == TicketLabel.ticket_id)
        .filter(Ticket.project_id == project_id, Ticket.deleted_at.is_(None))
        .group_by(TicketLabel.label_id)
        .all()
    )


@router.get("/projects/{ref}/labels", response_model=list[LabelOut])
def list_labels(project: ProjectByRef, db: DbDep, user: CurrentUser) -> list[LabelOut]:
    ensure_member(db, project, user)
    counts = _counts(db, project.id)
    rows = db.query(Label).filter(Label.project_id == project.id).order_by(Label.name).all()
    return [label_out(lb, counts.get(lb.id, 0)) for lb in rows]


@router.post(
    "/projects/{ref}/labels", response_model=LabelOut, status_code=status.HTTP_201_CREATED
)
def create_label(
    project: ProjectByRef, payload: LabelCreate, db: DbDep, user: CurrentUser
) -> LabelOut:
    ensure_project_lead(db, project, user)
    existing = (
        db.query(Label)
        .filter(Label.project_id == project.id, func.lower(Label.name) == payload.name)
        .first()
    )
    if existing is not None:
        raise conflict("LABEL_EXISTS", f"label {payload.name!r} already exists")
    label = Label(project_id=project.id, name=payload.name, color=payload.color)
    db.add(label)
    db.commit()
    db.refresh(label)
    return label_out(label, 0)


@router.patch("/labels/{label_id}", response_model=LabelOut)
def update_label(
    label_id: str, payload: LabelUpdate, db: DbDep, user: CurrentUser
) -> LabelOut:
    label = db.get(Label, label_id)
    if label is None:
        raise not_found("LABEL_NOT_FOUND", "label not found")
    ensure_project_lead(db, label.project, user)
    data = payload.model_dump(exclude_unset=True)
    if data.get("name"):
        name = data["name"].strip().lower()
        clash = (
            db.query(Label)
            .filter(
                Label.project_id == label.project_id,
                func.lower(Label.name) == name,
                Label.id != label.id,
            )
            .first()
        )
        if clash is not None:
            raise conflict("LABEL_EXISTS", f"label {name!r} already exists")
        label.name = name
    if data.get("color"):
        label.color = data["color"]
    db.add(label)
    db.commit()
    db.refresh(label)
    counts = _counts(db, label.project_id)
    return label_out(label, counts.get(label.id, 0))


@router.delete("/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label(label_id: str, db: DbDep, user: CurrentUser) -> None:
    label = db.get(Label, label_id)
    if label is None:
        raise not_found("LABEL_NOT_FOUND", "label not found")
    ensure_project_lead(db, label.project, user)
    db.query(TicketLabel).filter(TicketLabel.label_id == label.id).delete(
        synchronize_session=False
    )
    db.delete(label)
    db.commit()
