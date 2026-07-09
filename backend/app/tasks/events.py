"""Celery task for periodic current-event generation."""

import asyncio

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.config import get_settings

settings = get_settings()


@celery_app.task(name="app.tasks.events.generate_events")
def generate_events_task():
    """Run event generation in an async context."""
    async def _run():
        from app.services.event_generator import generate_events

        if "sqlite" in settings.DATABASE_URL:
            from app.core.database import _AsyncAdapter
            db = _AsyncAdapter(SessionLocal())
            try:
                result = await generate_events(db)
                return result
            finally:
                await db.close()
        else:
            async with SessionLocal() as session:
                result = await generate_events(session)
                return result

    return asyncio.run(_run())
