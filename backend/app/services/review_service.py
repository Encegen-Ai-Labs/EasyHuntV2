from datetime import datetime, timezone
from typing import Dict, Any, List
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.doc_repo import DocumentRepository
from app.repositories.base import BaseRepository
from app.core.exceptions import ResourceNotFoundError, PropertySystemException

class ReviewService:
    def __init__(
        self,
        case_repo: CaseRepository,
        flag_repo: FlagRepository,
        doc_repo: DocumentRepository | None = None,
        extraction_repo: BaseRepository | None = None,
    ):
        self.case_repo = case_repo
        self.flag_repo = flag_repo
        self.doc_repo = doc_repo
        self.extraction_repo = extraction_repo or BaseRepository(doc_repo.client)

    def assign_reviewer(self, case_id: str, reviewer_id: str) -> Dict[str, Any]:
        case_obj = self.case_repo.get_by_id(case_id)
        if not case_obj:
            raise ResourceNotFoundError("Target case not found")

        updated_case = self.case_repo.update_case(case_id, {
            "reviewer_id": reviewer_id,
            "status": "review",
        })
        for document in self.doc_repo.list_reviewable_by_case(case_id):
            self.doc_repo.update_status(document["id"], "under_review")
        return updated_case

    def get_case_documents_for_review(self, case_id: str) -> List[Dict[str, Any]]:
        if not self.case_repo.get_by_id(case_id):
            raise ResourceNotFoundError("Target case not found")

        review_documents = []
        for document in self.doc_repo.list_reviewable_by_case(case_id):
            extraction = self.extraction_repo.select_one(
                "extractions", {"document_id": document["id"]}
            )
            if extraction:
                extraction["handwriting_flagged"] = bool(
                    extraction.get("has_handwritten_content")
                )
            file_url = self.doc_repo.client.storage.from_("documents").create_signed_url(
                document["file_path"], 3600
            )["signedURL"]
            review_documents.append({
                "document": document,
                "file_url": file_url,
                "extraction": extraction,
            })
        return review_documents

    def submit_document_review(
        self,
        document_id: str,
        reviewer_id: str,
        validated_output: Dict[str, Any],
        review_notes: str | None,
        decision: str,
    ) -> Dict[str, Any]:
        document = self.doc_repo.get_by_id(document_id)
        if not document:
            raise ResourceNotFoundError("Document not found")
        extraction = self.extraction_repo.select_one(
            "extractions", {"document_id": document_id}
        )
        if not extraction:
            raise ResourceNotFoundError("AI extraction not found for document")
        if decision not in {"approved", "rejected"}:
            raise PropertySystemException("Decision must be approved or rejected")

        updated_extraction = self.extraction_repo.update(
            "extractions",
            {"id": extraction["id"]},
            {
                "validated_json_output": validated_output,
                "human_correction": validated_output,
                "review_notes": review_notes,
                "reviewed_by": reviewer_id,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
                "status": decision,
            },
        )
        updated_document = self.doc_repo.update_status(document_id, decision)
        return {
            "document": updated_document,
            "extraction": updated_extraction[0] if updated_extraction else None,
        }

    def resolve_flag(self, flag_id: str, user_id: str, resolution_notes: str, status: str) -> Dict[str, Any]:
        payload = {
            "status": status,
            "resolved_by": user_id,
            "resolution_notes": resolution_notes
        }
        return self.flag_repo.update_flag(flag_id, payload)

    def finalize_review(self, case_id: str, decision: str) -> Dict[str, Any]:
        case_obj = self.case_repo.get_by_id(case_id)
        if not case_obj:
            raise ResourceNotFoundError("Target case not found")

        if decision == "approve":
            self.case_repo.update_case(case_id, {"status": "completed"})
            if self.doc_repo:
                for document in self.doc_repo.list_by_case(case_id):
                    self.doc_repo.update_status(document["id"], "completed")
            return self.case_repo.get_by_id(case_id)

        self.case_repo.update_case(case_id, {"status": "review"})
        if self.doc_repo:
            for document in self.doc_repo.list_by_case(case_id):
                self.doc_repo.update_status(document["id"], "rejected")
        return self.case_repo.get_by_id(case_id)