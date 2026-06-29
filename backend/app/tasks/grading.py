"""Celery tasks for async essay grading."""

from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.grading.grade_essay_task")
def grade_essay_task(essay_id: str, question: str, answer: str):
    """Async task: grade an essay submission."""
    # TODO: 阶段四实现
    pass
