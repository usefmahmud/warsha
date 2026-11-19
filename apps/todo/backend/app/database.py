"""SQLite engine + session factory (WAL, sane busy timeout)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def make_engine(url: str, echo: bool = False) -> Engine:
    is_sqlite = url.startswith("sqlite")
    kwargs: dict = {"echo": echo, "future": True}
    if is_sqlite:
        kwargs["connect_args"] = {"check_same_thread": False, "timeout": 15}
    eng = create_engine(url, **kwargs)

    if is_sqlite:

        @event.listens_for(eng, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):  # type: ignore[no-redef]
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA synchronous=NORMAL")
            cur.execute("PRAGMA busy_timeout=15000")
            cur.close()

    return eng


engine = make_engine(settings.database_url, settings.sql_echo)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create the schema. Idempotent — safe on every boot."""
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
