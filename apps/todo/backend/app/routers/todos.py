"""Todo CRUD API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..errors import invalid, not_found
from ..models import PRIORITY_ORDER, Todo, TodoPriority, utcnow
from ..schemas import TodoCreate, TodoListOut, TodoOut, TodoUpdate

router = APIRouter(prefix="/todos", tags=["todos"])


def _get_or_404(db: Session, todo_id: str) -> Todo:
    todo = db.get(Todo, todo_id)
    if todo is None:
        raise not_found("TODO_NOT_FOUND", f"todo {todo_id} not found")
    return todo


def _sort_key(todo: Todo):
    return (
        todo.done,
        PRIORITY_ORDER.get(todo.priority, 1),
        -todo.created_at.timestamp(),
    )


@router.get("", response_model=TodoListOut, summary="List todos with filters")
def list_todos(
    done: bool | None = Query(default=None, description="true = done only, false = open only"),
    q: str | None = Query(default=None, max_length=200, description="search in title and notes"),
    priority: TodoPriority | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
) -> TodoListOut:
    stmt = select(Todo)
    if done is not None:
        stmt = stmt.where(Todo.done.is_(done))
    if priority is not None:
        stmt = stmt.where(Todo.priority == priority)
    if q:
        needle = f"%{q.strip()}%"
        stmt = stmt.where(or_(Todo.title.ilike(needle), Todo.notes.ilike(needle)))

    rows = list(db.scalars(stmt))
    rows.sort(key=_sort_key)
    rows = rows[:limit]

    # Counters always describe the whole board, not the filtered slice.
    done_count = db.query(Todo).filter(Todo.done.is_(True)).count()
    total = db.query(Todo).count()

    return TodoListOut(
        items=[TodoOut(**t.to_dict()) for t in rows],
        count=len(rows),
        open_count=total - done_count,
        done_count=done_count,
    )


@router.post(
    "", response_model=TodoOut, status_code=status.HTTP_201_CREATED, summary="Create a todo"
)
def create_todo(payload: TodoCreate, db: Session = Depends(get_db)) -> TodoOut:
    todo = Todo(
        title=payload.title,
        notes=payload.notes,
        priority=TodoPriority(payload.priority),
        due_date=payload.due_date,
        done=False,
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return TodoOut(**todo.to_dict())


@router.get("/{todo_id}", response_model=TodoOut, summary="Fetch one todo")
def get_todo(todo_id: str, db: Session = Depends(get_db)) -> TodoOut:
    return TodoOut(**_get_or_404(db, todo_id).to_dict())


@router.patch("/{todo_id}", response_model=TodoOut, summary="Partial update")
def update_todo(todo_id: str, payload: TodoUpdate, db: Session = Depends(get_db)) -> TodoOut:
    todo = _get_or_404(db, todo_id)
    sent = payload.model_fields_set
    if not sent:
        raise invalid("EMPTY_PATCH", "send at least one field to update")

    if "title" in sent and payload.title is not None:
        todo.title = payload.title
    if "notes" in sent:
        todo.notes = payload.notes
    if "done" in sent and payload.done is not None:
        todo.done = payload.done
    if "priority" in sent and payload.priority is not None:
        todo.priority = TodoPriority(payload.priority)
    if "due_date" in sent:
        todo.due_date = payload.due_date

    todo.updated_at = utcnow()
    db.commit()
    db.refresh(todo)
    return TodoOut(**todo.to_dict())


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a todo")
def delete_todo(todo_id: str, db: Session = Depends(get_db)) -> Response:
    todo = _get_or_404(db, todo_id)
    db.delete(todo)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{todo_id}/toggle", response_model=TodoOut, summary="Flip the done flag")
def toggle_todo(todo_id: str, db: Session = Depends(get_db)) -> TodoOut:
    todo = _get_or_404(db, todo_id)
    todo.done = not todo.done
    todo.updated_at = utcnow()
    db.commit()
    db.refresh(todo)
    return TodoOut(**todo.to_dict())
