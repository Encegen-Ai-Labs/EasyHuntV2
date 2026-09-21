from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.exceptions import PropertySystemException, ResourceNotFoundError
from app.repositories.doc_repo import DocumentRepository
from app.repositories.report_excerpt_repo import ReportExcerptRepository
from app.repositories.report_repo import ReportRepository
from app.services.doc_service import DocumentService
from app.services.report_pdf_builder import build_excerpt_report_pdf
from app.services.translation_service import translate_to_english

REPORT_TYPE = "manual"
REPORTS_BUCKET = "reports"  # same Supabase Storage bucket report_service.py's PDF-summary flow uses


class ReportBuilderService:
    def __init__(
        self,
        doc_service: DocumentService,
        report_repo: ReportRepository,
        excerpt_repo: ReportExcerptRepository,
        doc_repo: DocumentRepository,
    ):
        self.doc_service = doc_service
        self.report_repo = report_repo
        self.excerpt_repo = excerpt_repo
        self.doc_repo = doc_repo

    def get_or_create_report(self, case_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        # Reuses the same case-ownership rule as upload/search instead of a
        # fourth copy of it.
        self.doc_service.authorize_case_access(case_id, current_user)

        existing = self.report_repo.get_by_case_and_type(case_id, REPORT_TYPE)
        if existing:
            return existing

        return self.report_repo.create_report({
            "case_id": case_id,
            "report_type": REPORT_TYPE,
            "status": "draft",
            "generated_by": current_user["id"],
            # A brand-new report obviously hasn't been approved by anyone yet.
            # Explicit, not just correctness — the live reports table has a
            # stray DEFAULT on approved_by pointing at a UUID that no longer
            # exists in users, which fires (and breaks the insert with a FK
            # violation) whenever this key is omitted instead of set to null.
            "approved_by": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_report_with_excerpts(self, case_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        report = self.get_or_create_report(case_id, current_user)
        excerpts = self.excerpt_repo.list_by_report(report["id"])

        # Denormalize document_name onto each excerpt so the report-builder UI
        # doesn't need a second round trip (or a raw UUID) per excerpt.
        doc_lookup = {doc["id"]: doc for doc in self.doc_repo.list_by_case(case_id)}
        for excerpt in excerpts:
            document = doc_lookup.get(excerpt["document_id"])
            excerpt["document_name"] = document.get("file_name") if document else None

        return {**report, "excerpts": excerpts}

    def add_excerpt(
        self,
        case_id: str,
        document_id: str,
        page_number: int,
        excerpt_text: str,
        note: Optional[str],
        current_user: Dict[str, Any],
    ) -> Dict[str, Any]:
        report = self.get_or_create_report(case_id, current_user)

        # The excerpt's document must actually belong to this case — otherwise a
        # stale UI tab pointed at the wrong case could silently cite an
        # unrelated case's document.
        document = self.doc_repo.get_by_id(document_id)
        if not document or str(document.get("case_id")) != str(case_id):
            raise ResourceNotFoundError("Document not found in this case")

        existing_excerpts = self.excerpt_repo.list_by_report(report["id"])
        next_order = (existing_excerpts[-1]["sequence_order"] + 1) if existing_excerpts else 0

        return self.excerpt_repo.create({
            "report_id": report["id"],
            "document_id": document_id,
            "page_number": page_number,
            "excerpt_text": excerpt_text,
            "sequence_order": next_order,
            "note": note,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    def remove_excerpt(self, case_id: str, excerpt_id: str, current_user: Dict[str, Any]) -> None:
        report = self.get_or_create_report(case_id, current_user)
        excerpt = self._get_owned_excerpt(report["id"], excerpt_id)
        self.excerpt_repo.delete_excerpt(excerpt["id"])

    def update_excerpt_note(
        self,
        case_id: str,
        excerpt_id: str,
        note: Optional[str],
        current_user: Dict[str, Any],
        excerpt_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """excerpt_text lets the reviewer correct the excerpt's own wording
        (e.g. an OCR/VLM transcription slip) — kept optional and alongside
        note in the same call, distinct from the extraction-fields edit path
        (ReviewService.submit_document_review), which edits the underlying
        AI extraction rather than a cited excerpt."""
        report = self.get_or_create_report(case_id, current_user)
        excerpt = self._get_owned_excerpt(report["id"], excerpt_id)

        fields: Dict[str, Any] = {"note": note}
        if excerpt_text is not None:
            fields["excerpt_text"] = excerpt_text
        return self.excerpt_repo.update_fields(excerpt["id"], fields)

    def reorder_excerpts(
        self, case_id: str, excerpt_ids: List[str], current_user: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        report = self.get_or_create_report(case_id, current_user)
        existing = self.excerpt_repo.list_by_report(report["id"])
        existing_ids = {e["id"] for e in existing}

        if set(excerpt_ids) != existing_ids:
            raise PropertySystemException("Reorder list must include exactly the report's current excerpts")

        for index, excerpt_id in enumerate(excerpt_ids):
            self.excerpt_repo.update_sequence(excerpt_id, index)

        return self.excerpt_repo.list_by_report(report["id"])

    def export_pdf(self, case_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        result = self.get_report_with_excerpts(case_id, current_user)
        case = self.doc_service.case_repo.get_by_id(case_id) or {"id": case_id}

        # Translate every excerpt to English for the exported PDF (user's
        # explicit choice, 2026-08-21 — every excerpt always shows both
        # languages). Excerpts carry no language tag and are just whatever
        # text the reviewer selected/edited, so translating fresh here rather
        # than reusing whatever page-level english_text may or may not exist
        # keeps the PDF accurate to the excerpt's actual current text. One
        # Translate API call per excerpt per export; a failed translation
        # doesn't block the export, same fallback-sentinel pattern as
        # translation_service.translate_pages().
        excerpts_with_translation: List[Dict[str, Any]] = []
        for excerpt in result["excerpts"]:
            translation = translate_to_english(excerpt.get("excerpt_text", ""))
            english_text = (
                translation["translated_text"]
                if translation["success"]
                else f"[translation failed: {translation['error']}]"
            )
            excerpts_with_translation.append({**excerpt, "english_text": english_text})

        pdf_bytes = build_excerpt_report_pdf(case, excerpts_with_translation)

        # Distinct path from report_service.py's PDF-summary flow
        # (reports/{case_id}/verification_report.pdf) so the two don't collide.
        storage_path = f"reports/{case_id}/manual/report.pdf"
        self.report_repo.client.storage.from_(REPORTS_BUCKET).upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "x-upsert": "true"},
        )
        self.report_repo.update_file_path(result["id"], storage_path)

        signed_url = self.report_repo.client.storage.from_(REPORTS_BUCKET).create_signed_url(
            storage_path, 3600
        )["signedURL"]

        return {"file_path": storage_path, "download_url": signed_url}

    def _get_owned_excerpt(self, report_id: str, excerpt_id: str) -> Dict[str, Any]:
        excerpt = self.excerpt_repo.get_by_id(excerpt_id)
        if not excerpt or str(excerpt.get("report_id")) != str(report_id):
            raise ResourceNotFoundError("Excerpt not found in this report")
        return excerpt
