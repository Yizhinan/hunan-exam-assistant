"""FastAPI application entry point — 湖南公务员考试助手."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import engine, Base
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
    # Create tables on startup
    Base.metadata.create_all(bind=engine)
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
