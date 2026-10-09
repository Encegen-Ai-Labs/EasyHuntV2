from celery import Celery

from app.core.config import settings

# Absolute ceiling regardless of configuration: one misconfigured env var must
# not turn into dozens of simultaneous Gemini calls.
WORKER_CONCURRENCY_CAP = 6

celery_app = Celery(
    "easyhuntv2",
    include=["app.tasks.document_tasks"],
    broker=settings.CELERY_BROKER_URL,
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    # Status is read from the documents table, never from task results.
    task_ignore_result=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    worker_concurrency=max(1, min(settings.CELERY_WORKER_CONCURRENCY, WORKER_CONCURRENCY_CAP)),
    task_time_limit=3600,
    task_soft_time_limit=3300,
)
