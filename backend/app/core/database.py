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

        # users: is_admin column (2025-07)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(users)")}
        if "is_admin" not in existing:
            conn.execute("ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0 NOT NULL")
            logger.info("Migration: added column users.is_admin")
        conn.commit()

        # current_events table (2026-07)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS current_events (
                    id VARCHAR(36) PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    description TEXT NOT NULL,
                    event_date DATE NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    relevance VARCHAR(20) NOT NULL DEFAULT '了解',
                    source VARCHAR(500),
                    year INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

            conn.execute("CREATE INDEX IF NOT EXISTS ix_current_events_year ON current_events(year)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_current_events_category ON current_events(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS ix_current_events_relevance ON current_events(relevance)")
            conn.commit()
        except Exception:
            pass  # table already exists
    finally:
        conn.close()


async def _migrate_postgres():
    """Add missing columns to PostgreSQL for model changes."""
    if "sqlite" in settings.DATABASE_URL:
        return

    from sqlalchemy import text
    async with engine.begin() as conn:
        # users: is_admin column (2025-07)
        result = await conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='users' AND column_name='is_admin'"
        ))
        if not result.fetchone():
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT false NOT NULL"
            ))
            logger.info("Migration (PG): added column users.is_admin")

        # current_events table (2026-07)
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_name='current_events'"
        ))
        if not result.fetchone():
            await conn.execute(text("""
                CREATE TABLE current_events (
                    id VARCHAR(36) PRIMARY KEY,
                    title VARCHAR(500) NOT NULL,
                    description TEXT NOT NULL,
                    event_date DATE NOT NULL,
                    category VARCHAR(50) NOT NULL,
                    relevance VARCHAR(20) NOT NULL DEFAULT '了解',
                    source VARCHAR(500),
                    year INTEGER NOT NULL,
                    is_active BOOLEAN DEFAULT true NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_current_events_year ON current_events(year)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_current_events_category ON current_events(category)"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_current_events_relevance ON current_events(relevance)"
            ))
            logger.info("Migration (PG): created table current_events")


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
