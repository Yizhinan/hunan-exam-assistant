"""Celery task for periodic current-event generation."""

import asyncio

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import get_settings

settings = get_settings()


@celery_app.task(name="generate-events-weekly")
def generate_events_task():
    """Run event generation in an async context."""
    async def _run():
        from app.services.event_generator import generate_events

        if "sqlite" in settings.DATABASE_URL:
            from app.core.database import _AsyncAdapter
            db = _AsyncAdapter(SessionLocal())
        else:
            async with SessionLocal() as session:
                db = session
                await generate_events(db)
                return

        try:
            await generate_events(db)
        finally:
            await db.close()

    asyncio.get_event_loop().run_until_complete(_run())
