"""FastAPI application entry point — 湖南公务员考试助手."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base, SessionLocal
from app.api import auth, essay, knowledge, daily, analysis

# Import models so they register with Base.metadata for auto-create
import app.models.user  # noqa: F401
import app.models.document  # noqa: F401
import app.models.essay  # noqa: F401
import app.models.daily_essay  # noqa: F401
import app.models.position  # noqa: F401

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    # Apply SQLite schema migrations (new columns for model changes)
    from app.core.database import _migrate_sqlite
    _migrate_sqlite()
    # Create tables on startup — handle both async (PostgreSQL) and sync (SQLite) engines
    if "sqlite" in settings.DATABASE_URL:
        # Sync engine (SQLite)
        with engine.begin() as conn:
            Base.metadata.create_all(conn)
    else:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- routers ----------

app.include_router(auth.router)
app.include_router(essay.router)
app.include_router(knowledge.router)
app.include_router(daily.router)
app.include_router(analysis.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
