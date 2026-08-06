import json
from typing import Dict, Any
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.base import BaseRepository
from app.services.llm_extractor import extract_from_supabase_url
from app.services.doc_service import STORAGE_BUCKET

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

    def execute_analysis_pipeline(self, doc_id: str) -> Dict[str, Any]:
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
        # get signed url from supabase storage to pass to gemini
        file_url = self.generic_repo.client.storage.from_(
            STORAGE_BUCKET
        ).create_signed_url(doc["file_path"], 300)["signedURL"]

        result = extract_from_supabase_url(file_url)

        if not result["success"]:
            self.doc_repo.update_status(doc_id, "processing")
            self.case_repo.update_case(case_id, {"status": "processing"})
            return {
                "status": "processing",
                "case_id": case_id,
                "document_id": doc_id,
                "error": result["error"]
            }

        extracted = result["extracted"]
        raw_json = extracted
        validated_json = extracted

        extraction_payload = {
            "document_id": doc_id,
            "raw_ocr_text": result["raw_output"],
            "raw_json_output": raw_json,
            "validated_json_output": validated_json,
            "confidence_score": {
                "high": 95.0,
                "medium": 70.0,
                "low": 40.0
            }.get(extracted.get("confidence", "low"), 40.0),
            "model_used": result["model_used"]
        }

        self.generic_repo.insert("extractions", extraction_payload)

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

        handwriting_detected = False
        for key in ["handwriting_detected", "contains_handwriting", "has_handwriting"]:
            value = extracted.get(key)
            if isinstance(value, bool) and value:
                handwriting_detected = True
                break
            if isinstance(value, str) and value.lower() in {"true", "yes", "y", "1"}:
                handwriting_detected = True
                break

        if handwriting_detected:
            self.doc_repo.update_status(doc_id, "flagged")
            self.case_repo.update_case(case_id, {"status": "review"})
            return {
                "status": "flagged",
                "case_id": case_id,
                "document_id": doc_id,
                "extracted": extracted
            }

        self.doc_repo.update_status(doc_id, "processing")
        self.case_repo.update_case(case_id, {"status": "review"})

        return {
            "status": "processing",
            "case_id": case_id,
            "document_id": doc_id,
            "extracted": extracted
        }