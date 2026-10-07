from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "easyhuntv2",
    include=["app.tasks.document_tasks"],
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=3600,
    task_soft_time_limit=3300,
    result_expires=3600,
)
