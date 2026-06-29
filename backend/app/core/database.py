"""SQLAlchemy engine and session configuration — sync for SQLite, async for PostgreSQL."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

if "sqlite" in settings.DATABASE_URL:
    # SQLite: use sync engine (avoids greenlet issues on Windows)
    engine = create_engine(
        settings.DATABASE_URL.replace("+aiosqlite", "").replace("sqlite+aiosqlite:///", "sqlite:///"),
        echo=settings.DEBUG,
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    # PostgreSQL: use async engine (requires greenlet)
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def get_db():
    """
    Dependency — yields a DB session.
    Works with both sync (SQLite) and async (PostgreSQL) engines.
    """
    if "sqlite" in settings.DATABASE_URL:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        # Async generator for FastAPI
        async def _get_async_db():
            async with SessionLocal() as session:
                yield session
        return _get_async_db()
