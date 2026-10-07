from typing import Any, Dict

from app.core.logging import logger
from app.dependencies.db import get_supabase_client
from app.repositories.case_repo import CaseRepository
from app.repositories.doc_repo import DocumentRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.repositories.flag_repo import FlagRepository
from app.services.pipeline_service import PipelineService
from app.tasks.celery_app import celery_app


def _pipeline_service() -> PipelineService:
    db = get_supabase_client()
    return PipelineService(
        DocumentRepository(db),
        CaseRepository(db),
        FlagRepository(db),
        DocumentPageRepository(db),
    )


@celery_app.task(
    bind=True,
    name="documents.process",
    max_retries=2,
    default_retry_delay=15,
    acks_late=True,
)
def process_document_task(self: Any, document_id: str) -> Dict[str, str]:
    """Process one uploaded document; worker concurrency parallelizes a batch."""
    service = None
    try:
        service = _pipeline_service()
        result = service.execute_analysis_pipeline(document_id)
        return {"document_id": document_id, "status": result.get("status", "success")}
    except Exception as exc:
        if self.request.retries < self.max_retries:
            logger.exception(
                "documents.task_failed_retrying | document_id=%s retry=%s",
                document_id,
                self.request.retries + 1,
            )
            raise self.retry(exc=exc)

        logger.exception("documents.task_failed | document_id=%s", document_id)
        try:
            service = service or _pipeline_service()
            service.doc_repo.update_status(document_id, "flagged")
        except Exception:
            logger.exception(
                "documents.task_failure_status_update_failed | document_id=%s",
                document_id,
            )
        raise
