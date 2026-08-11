from typing import Dict, Any
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.base import BaseRepository
from app.services.llm_extractor import extract_from_supabase_url
from app.services.doc_service import STORAGE_BUCKET
from app.services.validation import validate_extraction
from app.services.chain_service import ChainReconstructionService
from app.services.risk_service import RiskFlaggingService
from app.services.report_draft_service import generate_draft_report


class PipelineService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        case_repo: CaseRepository,
        flag_repo: FlagRepository
    ):
        self.doc_repo = doc_repo
        self.case_repo = case_repo
        self.flag_repo = flag_repo
        self.generic_repo = BaseRepository(doc_repo.client)
        self.chain_service = ChainReconstructionService(self.generic_repo)
        self.risk_service = RiskFlaggingService(flag_repo, self.chain_service)

    def execute_analysis_pipeline(self, doc_id: str) -> Dict[str, Any]:
        # Check if this document was already processed - avoid duplicate LLM calls
        existing = self.generic_repo.select("extractions", {"document_id": doc_id})
        if existing:
            return {
                "status": "already_processed",
                "case_id": self.doc_repo.get_by_id(doc_id)["case_id"],
                "document_id": doc_id,
                "extracted": existing[0]["validated_json_output"]
            }

        # Transition document status to processing
        self.doc_repo.update_status(doc_id, "processing")
        doc = self.doc_repo.get_by_id(doc_id)
        if not doc:
            return {
                "status": "failed",
                "document_id": doc_id,
                "error": "Document not found"
            }
        case_id = doc["case_id"]

        self.case_repo.update_case(case_id, {"status": "processing"})

        # Step 1 & 2: Real LLM extraction via Gemini
        file_url = self.generic_repo.client.storage.from_(
            STORAGE_BUCKET
        ).create_signed_url(doc["file_path"], 300)["signedURL"]

        result = extract_from_supabase_url(file_url)

        if not result["success"]:
            self.doc_repo.update_status(doc_id, "flagged")
            return {
                "status": "failed",
                "case_id": case_id,
                "document_id": doc_id,
                "error": result["error"]
            }

        extracted = result["extracted"]
        raw_json = extracted
        validated_json = extracted

        # Run validation — includes handwriting override rule
        validation_result = validate_extraction(extracted)

        extraction_payload = {
            "document_id": doc_id,
            "raw_ocr_text": result["raw_output"],
            "raw_json_output": raw_json,
            "validated_json_output": validated_json,
            "confidence": extracted.get("overall_confidence", "low"),
            "model_used": result["model_used"],
            "validation_errors": validation_result["errors"] + validation_result["warnings"],
            "needs_review": validation_result["needs_human_review"],
            "has_handwritten_content": extracted.get("has_handwritten_content", True)
        }

        self.generic_repo.insert("extractions", extraction_payload)

        # Route based on validation instead of always going to under_review
        if validation_result["needs_human_review"]:
            self.doc_repo.update_status(doc_id, "flagged")
        else:
            self.doc_repo.update_status(doc_id, "llm_done")

        # Step 3: Populate Ownership Chain Records
        chain = extracted.get("chain", [])
        for record in chain:
            self.generic_repo.insert("ownership_chain", {
                "case_id": case_id,
                "sequence_order": record.get("order"),
                "owner_name": record.get("owner"),
                "transaction_date": record.get("date"),
                "transaction_type": record.get("type"),
                "survey_number": record.get("survey")
            })

        # Step 4: Run Flag Analyzer Engine
        base_survey = extracted.get("survey_number")
        for record in chain:
            if base_survey and record.get("survey") != base_survey:
                self.flag_repo.create_flag({
                    "case_id": case_id,
                    "flag_type": "Survey Number Mismatch",
                    "severity": "high",
                    "description": f"Chain link {record.get('order')} has survey {record.get('survey')} instead of {base_survey}",
                    "status": "raised"
                })

        # Finalize
        self.case_repo.update_case(case_id, {"status": "review"})

        return {
            "status": "success",
            "case_id": case_id,
            "document_id": doc_id,
            "extracted": extracted,
            "needs_review": validation_result["needs_human_review"]
        }

    def finalize_case(self, case_id: str) -> Dict[str, Any]:
        """
        Call this once all documents in a case have been processed.
        Runs case-level chain reconstruction, risk checks, and drafts the report.
        """
        chain_result = self.chain_service.reconstruct_case_chain(case_id)
        risk_flags = self.risk_service.run_case_level_checks(case_id)

        docs = self.doc_repo.list_by_case(case_id)

        draft_result = generate_draft_report(
            case_id=case_id,
            document_count=len(docs),
            chain_records=chain_result["chain"],
            flags=risk_flags
        )

        if draft_result["success"]:
            self.generic_repo.insert("reports", {
                "case_id": case_id,
                "llm_draft": draft_result["draft_text"],
                "status": "draft"
            })
            self.case_repo.update_case(case_id, {"status": "review"})

        return {
            "case_id": case_id,
            "chain": chain_result,
            "flags_raised": len(risk_flags),
            "report_generated": draft_result["success"]
        }