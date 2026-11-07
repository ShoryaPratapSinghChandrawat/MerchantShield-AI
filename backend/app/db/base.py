"""Database engine, session factory and declarative base.

SQLite is used for the whole project. Two SQLite-specific details are handled
here rather than scattered through the code:

1. ``check_same_thread=False`` so FastAPI's threadpool can share the connection.
2. ``PRAGMA foreign_keys=ON`` on every connection. SQLite disables foreign-key
   enforcement by default, which would silently break the foreign-key-safe
   delete ordering that ``POST /api/demo/reset`` depends on (section 6).
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.core.config import get_settings
from app.core.timeutil import ensure_utc
from app.db.sqlite_url import is_sqlite_url, sqlite_parent_dir


class UtcDateTime(TypeDecorator[datetime]):
    """A DateTime column that is always timezone-aware UTC in Python.

    SQLite cannot store an offset, so values are written as naive UTC and
    re-tagged as UTC when they are read back. Without this, ``created_at``
    would come out of the database naive and the API would emit a timestamp
    with no ``Z``.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return ensure_utc(value).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        return ensure_utc(value)


class Base(DeclarativeBase):
    """Declarative base for all MerchantShield models."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def _is_sqlite(url: str) -> bool:
    return is_sqlite_url(url)


def _ensure_sqlite_parent_dir(url: str) -> None:
    """Create the directory that will hold a SQLite file, if it is missing.

    SQLite raises ``unable to open database file`` when the parent directory
    does not exist, which is confusing and looks like a permissions problem.
    This matters in practice: the end-to-end run points DATABASE_URL at
    ``artifacts/phase-0/<env>/`` and a freshly extracted ZIP has no
    ``artifacts/`` folder at all.

    In-memory databases and non-file URLs are left alone. The URL grammar is
    parsed by :mod:`app.db.sqlite_url`, which is unit tested against Windows
    drive-letter forms.
    """
    parent = sqlite_parent_dir(url)
    if parent is not None:
        parent.mkdir(parents=True, exist_ok=True)


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""
    global _engine, _SessionLocal
    if _engine is None:
        url = get_settings().database_url
        _ensure_sqlite_parent_dir(url)
        connect_args = {"check_same_thread": False} if _is_sqlite(url) else {}
        _engine = create_engine(url, connect_args=connect_args, future=True)

        if _is_sqlite(url):

            @event.listens_for(_engine, "connect")
            def _enable_sqlite_foreign_keys(dbapi_connection: Any, _record: Any) -> None:
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None  # set by get_engine()
    return _SessionLocal


def init_db() -> None:
    """Create any missing tables. Safe to call repeatedly."""
    # Importing the models module registers every mapper on ``Base.metadata``.
    from app import models  # noqa: F401  (import for side effects)

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_engine_for_tests() -> None:
    """Dispose the engine so a test can point DATABASE_URL somewhere else."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
