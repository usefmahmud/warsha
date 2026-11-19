"""Mentions parser (PRD §5.3): ignores code spans/blocks and markdown links."""

from __future__ import annotations

import re

from sqlalchemy.orm import Session

from ..models import Comment, Mention, Ticket, User
from .events import notify

MENTION_RE = re.compile(r"(?<![\w@])@([a-z0-9_]{3,32})\b")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")
MD_LINK_RE = re.compile(r"\[[^\]]*\]\([^)]*\)")


def strip_code_and_links(text: str) -> str:
    """Remove fenced blocks, inline code and link targets before parsing mentions."""
    text = FENCED_CODE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = MD_LINK_RE.sub(" ", text)
    return text


def extract_mentions(*texts: str | None) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for text in texts:
        if not text:
            continue
        for match in MENTION_RE.finditer(strip_code_and_links(text)):
            name = match.group(1).rstrip("._-")
            if len(name) < 3 or name in seen:
                continue
            seen.add(name)
            found.append(name)
    return found


def resolve(db: Session, usernames: list[str]) -> list[User]:
    if not usernames:
        return []
    rows = db.query(User).filter(User.username.in_(usernames), User.is_active.is_(True)).all()
    by_name = {u.username: u for u in rows}
    return [by_name[n] for n in usernames if n in by_name]


def snippet(text: str, limit: int = 160) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= limit else flat[: limit - 1] + "…"


def record_mentions(
    db: Session,
    *,
    ticket: Ticket,
    actor: User,
    text: str,
    comment: Comment | None = None,
) -> list[User]:
    """Persist mention rows + notifications. Idempotent per (comment, user)."""
    users = resolve(db, extract_mentions(text))
    notified: list[User] = []
    for user in users:
        if comment is not None:
            exists = (
                db.query(Mention.id)
                .filter(
                    Mention.comment_id == comment.id,
                    Mention.mentioned_user_id == user.id,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                Mention(
                    ticket_id=ticket.id,
                    comment_id=comment.id,
                    mentioned_user_id=user.id,
                )
            )
        else:
            # description mentions are deduped per ticket (AC-12.7)
            exists = (
                db.query(Mention.id)
                .filter(
                    Mention.ticket_id == ticket.id,
                    Mention.comment_id.is_(None),
                    Mention.mentioned_user_id == user.id,
                )
                .first()
            )
            if exists:
                continue
            db.add(Mention(ticket_id=ticket.id, comment_id=None, mentioned_user_id=user.id))

        if user.id == actor.id:
            db.flush()
            continue  # self mentions are recorded but never notified (AC-12.5)

        note = notify(
            db,
            user_id=user.id,
            actor_id=actor.id,
            ticket=ticket,
            type="mention",
            payload={
                "ticket_key": ticket.key,
                "comment_id": comment.id if comment else None,
                "snippet": snippet(text),
            },
        )
        if note is not None:
            notified.append(user)
    db.flush()
    return notified
