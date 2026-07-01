"""SQLAlchemy engine and session configuration — sync for SQLite, async for PostgreSQL."""

import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

if "sqlite" in settings.DATABASE_URL:
    # SQLite: use sync engine (avoids greenlet issues on Windows)
    engine = create_engine(
        settings.DATABASE_URL.replace("+aiosqlite", "").replace("sqlite+aiosqlite:///", "sqlite:///"),
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    class _AsyncAdapter:
        """Wraps a sync SQLAlchemy session so that execute() and commit() can be awaited.

        This lets all endpoint code use ``await db.execute(...)`` / ``await db.commit()``
        regardless of whether the underlying session is sync (SQLite) or async (PostgreSQL).
        """

        def __init__(self, session):
            self._s = session

        async def execute(self, stmt, *args, **kwargs):
            return self._s.execute(stmt, *args, **kwargs)

        async def commit(self):
            return self._s.commit()

        async def rollback(self):
            return self._s.rollback()

        async def close(self):
            return self._s.close()

        async def refresh(self, obj, *args, **kwargs):
            return self._s.refresh(obj, *args, **kwargs)

        def add(self, obj):
            return self._s.add(obj)

        def add_all(self, objs):
            return self._s.add_all(objs)

        def delete(self, obj):
            return self._s.delete(obj)

        def flush(self):
            return self._s.flush()

        # Preserve hasattr(db, "query") for import functions that branch on it
        @property
        def query(self):
            return self._s.query

else:
    # PostgreSQL: use async engine (requires greenlet)
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def _migrate_sqlite():
    """Add missing columns to SQLite for model changes (SQLite ALTER TABLE is limited).

    SQLAlchemy create_all only creates NEW tables; existing tables need manual migration.
    This runs at startup to ensure the schema matches the models.
    """
    if "sqlite" not in settings.DATABASE_URL:
        return

    import sqlite3
    db_url = settings.DATABASE_URL
    # Extract file path from sqlite:///... or sqlite+aiosqlite:///...
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if prefix in db_url:
            db_path = db_url.split(prefix, 1)[1]
            break
    else:
        return

    conn = sqlite3.connect(db_path)
    try:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(position_history)")}
        migrations = [
            ("org_category", "VARCHAR(50)"),
            ("preferred_essay_category", "VARCHAR(20)"),
        ]
        for col_name, col_type in migrations:
            if col_name not in existing:
                conn.execute(f"ALTER TABLE position_history ADD COLUMN {col_name} {col_type}")
                logger.info("Migration: added column position_history.%s", col_name)
        conn.commit()

        # essay_submissions: material column (2024-07)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(essay_submissions)")}
        if "material" not in existing:
            conn.execute("ALTER TABLE essay_submissions ADD COLUMN material TEXT")
            logger.info("Migration: added column essay_submissions.material")
        conn.commit()
    finally:
        conn.close()


async def get_db():
    """
    Dependency — yields a DB session.
    Works with both sync (SQLite) and async (PostgreSQL) engines.
    Sync sessions are wrapped in _AsyncAdapter so all callers can
    uniformly use ``await db.execute()`` / ``await db.commit()``.
    """
    if "sqlite" in settings.DATABASE_URL:
        db = _AsyncAdapter(SessionLocal())
        try:
            yield db
        finally:
            await db.close()
    else:
        async with SessionLocal() as session:
            yield session
