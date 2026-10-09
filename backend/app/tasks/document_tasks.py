import random
from typing import Any, Dict

from app.core.config import settings
from app.core.logging import logger
from app.dependencies.db import get_supabase_client
from app.repositories.case_repo import CaseRepository
from app.repositories.doc_repo import DocumentRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.repositories.flag_repo import FlagRepository
from app.services.pipeline_service import PipelineService
from app.services.rate_limit import RateLimited
from app.tasks.celery_app import celery_app

# Unexpected exceptions (DB/storage blips) get this many retries; Gemini
# rate-limits get settings.CELERY_RATE_LIMIT_RETRIES, with longer backoff.
UNEXPECTED_FAILURE_RETRIES = 2
UNEXPECTED_FAILURE_BASE_SECONDS = 15


def _pipeline_service() -> PipelineService:
    db = get_supabase_client()
    return PipelineService(
        DocumentRepository(db),
        CaseRepository(db),
        FlagRepository(db),
        DocumentPageRepository(db),
    )


def backoff_seconds(base: int, attempt: int) -> int:
    """Exponential backoff with up to 25% jitter, so a burst of rate-limited
    documents doesn't all retry in the same second."""
    delay = base * (2 ** attempt)
    return int(delay + random.uniform(0, delay * 0.25))


@celery_app.task(
    bind=True,
    name="documents.process",
    max_retries=max(UNEXPECTED_FAILURE_RETRIES, settings.CELERY_RATE_LIMIT_RETRIES),
    acks_late=True,
)
def process_document_task(self: Any, document_id: str) -> Dict[str, str]:
    """Process one uploaded document with the same pipeline the in-process path
    uses (PipelineService.execute_analysis_pipeline, as called per document by
    execute_batch); worker concurrency replaces execute_batch's semaphore."""
    service = None
    try:
        service = _pipeline_service()
        result = service.execute_analysis_pipeline(document_id)
    except Exception as exc:
        if self.request.retries < UNEXPECTED_FAILURE_RETRIES:
            logger.exception(
                "documents.task_failed_retrying | document_id=%s retry=%s",
                document_id, self.request.retries + 1,
            )
            raise self.retry(
                exc=exc,
                countdown=backoff_seconds(UNEXPECTED_FAILURE_BASE_SECONDS, self.request.retries),
            )

        logger.exception("documents.task_failed | document_id=%s", document_id)
        try:
            service = service or _pipeline_service()
            service.doc_repo.update_status(document_id, "flagged")
        except Exception:
            logger.exception(
                "documents.task_failure_status_update_failed | document_id=%s", document_id,
            )
        raise

    if result.get("status") == "failed" and result.get("rate_limited"):
        attempt = self.request.retries
        if attempt < settings.CELERY_RATE_LIMIT_RETRIES:
            countdown = backoff_seconds(settings.CELERY_RATE_LIMIT_BACKOFF_SECONDS, attempt)
            logger.warning(
                "documents.rate_limited_retrying | document_id=%s retry=%s countdown=%ss",
                document_id, attempt + 1, countdown,
            )
            # The pipeline flagged the document when it failed; show it as
            # in-progress again while it waits for its retry.
            try:
                (service or _pipeline_service()).doc_repo.update_status(document_id, "processing")
            except Exception:
                logger.exception(
                    "documents.rate_limit_status_reset_failed | document_id=%s", document_id,
                )
            raise self.retry(exc=RateLimited(result.get("error")), countdown=countdown)
        logger.error(
            "documents.rate_limited_giving_up | document_id=%s attempts=%s",
            document_id, attempt + 1,
        )

    return {"document_id": document_id, "status": result.get("status", "success")}
