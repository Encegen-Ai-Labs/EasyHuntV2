import json
from typing import Dict, Any, List
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.base import BaseRepository

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
        case_id = doc["case_id"]
        
        self.case_repo.update_case(case_id, {"status": "processing"})

        # Step 1: Simulate OCR Extraction
        ocr_text = f"OCR raw dump from document: {doc['file_name']}. Trace of transfer history."
        self.doc_repo.update_status(doc_id, "ocr_done")

        # Step 2: Simulate LLM extraction & validation
        raw_json = {
            "property": {"survey_number": "404-A", "address": "123 Sovereign Way"},
            "chain": [
                {"order": 1, "owner": "John Doe", "date": "2020-01-15", "type": "Sale Deed", "survey": "404-A"},
                {"order": 2, "owner": "Alice Smith", "date": "2022-05-10", "type": "Sale Deed", "survey": "404-A"},
                {"order": 3, "owner": "Bob Miller", "date": "2025-11-20", "type": "Sale Deed", "survey": "404-B"} -- Potential mismatch
            ]
        }
        validated_json = raw_json.copy()
        
        extraction_payload = {
            "document_id": doc_id,
            "raw_ocr_text": ocr_text,
            "raw_json_output": raw_json,
            "validated_json_output": validated_json,
            "confidence_score": 88.50
        }
        
        # Save results directly to extractions table
        self.generic_repo.insert("extractions", extraction_payload)
        self.doc_repo.update_status(doc_id, "llm_done")

        # Step 3: Populate Ownership Chain Records
        for record in validated_json["chain"]:
            self.generic_repo.insert("ownership_chain", {
                "case_id": case_id,
                "sequence_order": record["order"],
                "owner_name": record["owner"],
                "transaction_date": record["date"],
                "transaction_type": record["type"],
                "survey_number": record["survey"]
            })

        # Step 4: Run Flag Analyzer Engine
        # Generate automated flag if survey numbers do not align
        for record in validated_json["chain"]:
            if record["survey"] != "404-A":
                self.flag_repo.create_flag({
                    "case_id": case_id,
                    "flag_type": "Survey Number Mismatch",
                    "severity": "high",
                    "description": f"Chain link {record['order']} specifies survey {record['survey']} instead of baseline 404-A",
                    "status": "raised"
                })

        # Finalize processing and submit case for Review
        self.doc_repo.update_status(doc_id, "under_review")
        self.case_repo.update_case(case_id, {"status": "review"})
        
        return {"status": "success", "case_id": case_id, "document_id": doc_id}