"""Decides how freshly uploaded documents get processed, in one place.

Two ways to run the pipeline, never both for the same document:

* in-process (default, CELERY_ENABLED=false): FastAPI background task calling
  PipelineService.execute_batch, which runs documents with bounded concurrency.
* queued (CELERY_ENABLED=true): one Celery task per document; each task calls
  the same PipelineService.execute_analysis_pipeline that execute_batch calls,
  with the worker's concurrency setting replacing execute_batch's semaphore.

Whichever is used, a document must never be left in "processing" with nothing
going to work on it. If the queue cannot be reached, the document falls back to
the in-process path (loudly: an error-level log and a warning returned to the
caller), and only if even that is impossible is it marked "flagged".
"""

from dataclasses import dataclass, field
from typing import Any, List, Optional

from app.core.config import settings
from app.core.logging import logger

MODE_IN_PROCESS = "in_process"
MODE_QUEUED = "queued"
MODE_FALLBACK = "in_process_fallback"
MODE_FAILED = "failed"


@dataclass
class DispatchOutcome:
    mode: str = MODE_IN_PROCESS
    queued_ids: List[str] = field(default_factory=list)
    fallback_ids: List[str] = field(default_factory=list)
    failed_ids: List[str] = field(default_factory=list)
    warning: Optional[str] = None


def _mark_flagged(pipeline_service: Any, document_id: str) -> None:
    try:
        pipeline_service.doc_repo.update_status(document_id, "flagged")
    except Exception:
        logger.exception(
            "documents.dispatch_failure_status_update_failed | document_id=%s", document_id
        )


def dispatch_documents(
    document_ids: List[str], pipeline_service: Any, background_tasks: Any
) -> DispatchOutcome:
    outcome = DispatchOutcome()
    if not document_ids:
        return outcome

    if not settings.CELERY_ENABLED:
        if background_tasks is not None:
            background_tasks.add_task(pipeline_service.execute_batch, list(document_ids))
            outcome.mode = MODE_IN_PROCESS
        else:
            outcome.mode = MODE_FAILED
            outcome.failed_ids = list(document_ids)
            outcome.warning = "No background executor was available; documents were flagged."
            for document_id in document_ids:
                _mark_flagged(pipeline_service, document_id)
        return outcome

    last_error: Optional[BaseException] = None
    try:
        # Lazy: celery only has to be installed when the queue is enabled.
        from app.tasks.document_tasks import process_document_task
    except Exception as exc:
        process_document_task = None
        last_error = exc

    unqueued: List[str] = []
    for document_id in document_ids:
        if process_document_task is None:
            unqueued.append(document_id)
            continue
        try:
            process_document_task.delay(document_id)
            outcome.queued_ids.append(document_id)
        except Exception as exc:
            last_error = exc
            unqueued.append(document_id)

    if unqueued:
        reason = f"{type(last_error).__name__}: {last_error}" if last_error else "unknown"
        if background_tasks is not None:
            logger.error(
                "documents.QUEUE_UNAVAILABLE_FALLING_BACK_IN_PROCESS | count=%s document_ids=%s "
                "reason=%s | CELERY_ENABLED=true but the broker/worker could not be used; "
                "check Redis and the Celery worker",
                len(unqueued), unqueued, reason,
            )
            background_tasks.add_task(pipeline_service.execute_batch, unqueued)
            outcome.fallback_ids = unqueued
            outcome.warning = (
                "The document queue is unavailable, so these documents are being processed "
                "inside the API process instead. Check Redis and the Celery worker."
            )
        else:
            logger.error(
                "documents.QUEUE_UNAVAILABLE_NO_FALLBACK | count=%s document_ids=%s reason=%s",
                len(unqueued), unqueued, reason,
            )
            outcome.failed_ids = unqueued
            outcome.warning = (
                "The document queue is unavailable and no fallback was possible; "
                "these documents were flagged. Retry processing once the queue is back."
            )
            for document_id in unqueued:
                _mark_flagged(pipeline_service, document_id)

    if outcome.failed_ids:
        outcome.mode = MODE_FAILED
    elif outcome.fallback_ids:
        outcome.mode = MODE_FALLBACK
    else:
        outcome.mode = MODE_QUEUED
    return outcome
