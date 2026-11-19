"""Boards API — CRUD, autosave with optimistic concurrency, read-only share links."""

from __future__ import annotations

import base64
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import Board, utcnow
from ..schemas import (
    DEFAULT_DOC,
    BoardCreate,
    BoardOut,
    BoardSummary,
    BoardUpdate,
    ShareOut,
)

router = APIRouter(prefix="/api", tags=["boards"])


def _get_board_or_404(db: Session, board_id: str) -> Board:
    board = db.get(Board, board_id)
    if board is None:
        raise HTTPException(status_code=404, detail="البورد غير موجود")
    return board


def _doc_to_text(doc: dict) -> str:
    """Serialize the scene; reject documents above the configured ceiling."""
    text = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
    if len(text.encode("utf-8")) > settings.max_doc_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"مستند البورد أكبر من الحد المسموح ({settings.max_doc_bytes // 1024}KB)",
        )
    return text


def _share_url(request: Request, token: str) -> str:
    base = str(request.base_url).rstrip("/")
    return f"{base}/s/{token}"


@router.get("/boards", response_model=list[BoardSummary])
def list_boards(db: Session = Depends(get_db)):
    """Newest first — the board picker shows the most recent work at the top."""
    rows = db.scalars(select(Board).order_by(Board.updated_at.desc())).all()
    return [BoardSummary.from_orm_board(b) for b in rows]


@router.post("/boards", response_model=BoardOut, status_code=status.HTTP_201_CREATED)
def create_board(payload: BoardCreate, db: Session = Depends(get_db)):
    count = db.scalar(select(func.count()).select_from(Board)) or 0
    if count >= settings.max_boards:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"وصلت للحد الأقصى من البوردات ({settings.max_boards})",
        )

    board = Board(
        name=payload.name,
        color=payload.color,
        doc=json.dumps(payload.doc or DEFAULT_DOC, ensure_ascii=False, separators=(",", ":")),
        version=1,
    )
    db.add(board)
    db.commit()
    db.refresh(board)
    return BoardOut.from_orm_board(board)


@router.get("/boards/{board_id}", response_model=BoardOut)
def get_board(board_id: str, db: Session = Depends(get_db)):
    return BoardOut.from_orm_board(_get_board_or_404(db, board_id))


@router.patch("/boards/{board_id}", response_model=BoardOut)
def update_board(board_id: str, payload: BoardUpdate, db: Session = Depends(get_db)):
    """Autosave endpoint.

    When `version` is supplied it acts as an optimistic-concurrency check: a stale
    version means another tab/client wrote first, so we answer 409 and hand back the
    current server state instead of silently clobbering it.
    """
    board = _get_board_or_404(db, board_id)

    if payload.version is not None and payload.version != board.version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "البورد اتعدّل في مكان تاني — اعمل تحديث قبل الحفظ",
                "expected_version": board.version,
                "sent_version": payload.version,
                "board": BoardOut.from_orm_board(board).model_dump(),
            },
        )

    changed = False
    if payload.name is not None and payload.name != board.name:
        board.name = payload.name
        changed = True
    if payload.color is not None and payload.color != board.color:
        board.color = payload.color
        changed = True
    if payload.doc is not None:
        board.doc = _doc_to_text(payload.doc)
        changed = True
    if payload.thumb is not None and payload.thumb != board.thumb:
        board.thumb = payload.thumb
        changed = True

    if changed:
        board.version += 1
        board.updated_at = utcnow()
        db.commit()
        db.refresh(board)

    return BoardOut.from_orm_board(board)


@router.delete("/boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: str, db: Session = Depends(get_db)):
    board = _get_board_or_404(db, board_id)
    db.delete(board)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/boards/{board_id}/share", response_model=ShareOut)
def create_share(board_id: str, request: Request, db: Session = Depends(get_db)):
    """Idempotent: an existing token is returned rather than rotated."""
    board = _get_board_or_404(db, board_id)
    if not board.share_token:
        board.share_token = secrets.token_urlsafe(18)
        board.updated_at = utcnow()
        db.commit()
        db.refresh(board)
    return ShareOut(share_token=board.share_token, share_url=_share_url(request, board.share_token))


@router.delete("/boards/{board_id}/share", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(board_id: str, db: Session = Depends(get_db)):
    board = _get_board_or_404(db, board_id)
    if board.share_token:
        board.share_token = None
        board.updated_at = utcnow()
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/shared/{token}", response_model=BoardOut)
def get_shared_board(token: str, db: Session = Depends(get_db)):
    """Read-only view of a board through its share token."""
    board = db.scalar(select(Board).where(Board.share_token == token))
    if board is None:
        raise HTTPException(status_code=404, detail="رابط المشاركة غير صالح")
    return BoardOut.from_orm_board(board)


@router.get("/boards/{board_id}/thumb", include_in_schema=False)
def get_thumb(board_id: str, db: Session = Depends(get_db)):
    """Board thumbnail as a real image response (browser-cacheable on cards)."""
    board = _get_board_or_404(db, board_id)
    if not board.thumb:
        raise HTTPException(status_code=404, detail="مفيش صورة مصغّرة")
    payload = board.thumb.split(",", 1)[-1]
    try:
        raw = base64.b64decode(payload)
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="مفيش صورة مصغّرة") from None
    return Response(
        content=raw,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=60"},
    )
