import asyncio
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from app.core.logging import logger
from app.repositories.doc_repo import DocumentRepository
from app.repositories.case_repo import CaseRepository
from app.repositories.flag_repo import FlagRepository
from app.repositories.document_page_repo import DocumentPageRepository
from app.repositories.base import BaseRepository
from app.services.llm_extractor import extract_structured_fields_from_text
from app.services.doc_service import STORAGE_BUCKET, enhanced_page_image_path
from app.services.validation import validate_extraction
from app.services.chain_service import ChainReconstructionService
from app.services.risk_service import RiskFlaggingService
from app.services.report_draft_service import generate_draft_report
from app.services.page_extraction_service import download_and_rasterize, strip_annotation_tags
from app.services.image_enhancement import enhance_page_image_with_report
from app.services.document_router import route_and_extract_page
from app.services.embedding_service import embed_pages

# Batch upload (up to 20 files/case) can queue up to 20 background extraction
# runs from a single request. FastAPI's BackgroundTasks would otherwise run these
# unbounded, hammering the Gemini API at once — cap how many run concurrently.
MAX_CONCURRENT_EXTRACTIONS = 3

# Within one document, pages are enhanced/routed concurrently too (see
# _process_page/ThreadPoolExecutor below) rather than one at a time — a
# multi-page document where several pages fall back to the VLM was otherwise
# paying for each page's network round-trip back-to-back. Combined with
# MAX_CONCURRENT_EXTRACTIONS above, worst case is
# MAX_CONCURRENT_EXTRACTIONS * MAX_CONCURRENT_PAGES_PER_DOCUMENT calls to
# Gemini in flight at once (3*4=12 by default) — turn this down if that
# starts tripping Gemini rate limits.
MAX_CONCURRENT_PAGES_PER_DOCUMENT = 4


class PipelineService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        case_repo: CaseRepository,
        flag_repo: FlagRepository,
        doc_page_repo: DocumentPageRepository
    ):
        self.doc_repo = doc_repo
        self.case_repo = case_repo
        self.flag_repo = flag_repo
        self.doc_page_repo = doc_page_repo
        self.generic_repo = BaseRepository(doc_repo.client)
        self.chain_service = ChainReconstructionService(self.generic_repo)
        self.risk_service = RiskFlaggingService(flag_repo, self.chain_service)

    def _process_page(
        self, case_id: str, doc_id: str, index: int, page_image: bytes,
        also_extract_fields: bool = False,
    ) -> Dict[str, Any]:
        """Enhances, persists, and routes one page. Runs inside the
        ThreadPoolExecutor in execute_analysis_pipeline below — every step
        here already either returns a result dict or catches its own errors
        (route_and_extract_page never raises; the enhanced-image upload has
        its own try/except), so a single page failing doesn't need to be
        caught by name here — but see the as_completed loop below, which
        still guards future.result() in case something unexpected slips
        through.

        also_extract_fields is passed straight through to
        route_and_extract_page (see its docstring) — execute_analysis_pipeline
        only sets it True for single-page documents."""
        page_number = index + 1

        enhanced, enhance_report = enhance_page_image_with_report(page_image)
        if enhance_report.get("fallback"):
            logger.info(
                "pipeline.page_enhance_fallback | document_id=%s page=%s "
                "reason=could_not_decode_or_process_image, used original bytes",
                doc_id, page_number,
            )
        else:
            applied = [
                step for step, ran in (
                    ("deskew", enhance_report.get("deskewed")),
                    ("denoise", enhance_report.get("denoised")),
                    ("clahe", enhance_report.get("clahe_applied")),
                    ("sharpen", enhance_report.get("sharpened")),
                ) if ran
            ] or ["none (page already clean)"]
            logger.info(
                "pipeline.page_enhanced | document_id=%s page=%s steps=%s "
                "sharpness=%s contrast=%s noise_sigma=%s skew=%s",
                doc_id, page_number, "+".join(applied),
                enhance_report.get("sharpness"), enhance_report.get("contrast"),
                enhance_report.get("noise_sigma"), enhance_report.get("skew_angle"),
            )

        # Persist the enhanced image an Admin can later inspect via
        # GET /documents/{id}/pages/{page_number}/enhanced-image — this is
        # the exact bytes OCR/Gemini both read, not the raw rasterization,
        # so it's what actually explains a bad transcription if one shows
        # up. Isolated in its own try/except, same defensive pattern as
        # the document_pages insert / ownership_chain insert below: a
        # storage hiccup here shouldn't block extraction itself.
        try:
            self.generic_repo.client.storage.from_(STORAGE_BUCKET).upload(
                path=enhanced_page_image_path(case_id, doc_id, page_number),
                file=enhanced,
                file_options={"content-type": "image/png", "x-upsert": "true"},
            )
        except Exception as e:
            logger.error(
                "pipeline.enhanced_image_upload_failed | document_id=%s page=%s error=%s",
                doc_id, page_number, e,
            )

        route_started = time.monotonic()
        routed = route_and_extract_page(
            enhanced, page_number=page_number, also_extract_fields=also_extract_fields,
        )
        elapsed = time.monotonic() - route_started
        logger.info(
            "pipeline.page_routed | document_id=%s page=%s source=%s confidence=%s "
            "has_handwriting=%s elapsed=%.2fs%s",
            doc_id, routed["page_number"], routed["source"], routed["confidence"],
            routed["has_handwriting"], elapsed,
            (" issues=" + "; ".join(routed["issues"])) if routed["issues"] else "",
        )
        return routed

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

        pipeline_started = time.monotonic()
        logger.info("pipeline.document_started | document_id=%s", doc_id)

        # Transition document status to processing
        self.doc_repo.update_status(doc_id, "processing")
        doc = self.doc_repo.get_by_id(doc_id)
        if not doc:
            logger.error("pipeline.document_not_found | document_id=%s", doc_id)
            return {
                "status": "failed",
                "document_id": doc_id,
                "error": "Document not found"
            }
        case_id = doc["case_id"]

        self.case_repo.update_case(case_id, {"status": "processing"})

        file_url = self.generic_repo.client.storage.from_(
            STORAGE_BUCKET
        ).create_signed_url(doc["file_path"], 300)["signedURL"]

        # Step 1: Rasterize into one image per page, then enhance + route each
        # page independently — Tesseract (fast/cheap) for mostly-printed pages,
        # the VLM (Gemini) for pages with meaningful handwritten content or
        # where OCR's own confidence is too low to trust. See
        # app/services/document_router.py for the routing rule and
        # app/services/image_enhancement.py for what "enhance" does.
        try:
            page_images = download_and_rasterize(file_url, doc.get("mime_type", "application/pdf"))
        except Exception as e:
            logger.error("pipeline.rasterization_failed | document_id=%s error=%s", doc_id, e)
            self.doc_repo.update_status(doc_id, "flagged")
            return {
                "status": "failed",
                "case_id": case_id,
                "document_id": doc_id,
                "error": f"Failed to rasterize document: {e}"
            }

        logger.info("pipeline.rasterized | document_id=%s pages=%s", doc_id, len(page_images))

        # Pages are enhanced + routed concurrently (bounded — see
        # MAX_CONCURRENT_PAGES_PER_DOCUMENT above) instead of one at a time:
        # each page's work is either local CPU (OpenCV enhancement, which
        # releases the GIL) or a network round-trip (OCR subprocess, the VLM
        # call), so running several in parallel threads genuinely overlaps
        # their wall-clock time rather than just interleaving CPU-bound work.
        # routed_pages is pre-sized and filled by index rather than appended,
        # since results can complete out of order but merged_text below needs
        # them in page order.
        # Single-page documents get also_extract_fields=True (see
        # route_and_extract_page's docstring): if the page needs the VLM at
        # all, that one call also returns structured fields, so the
        # separate extract_structured_fields_from_text call below can be
        # skipped entirely — halving Gemini round-trips for what's likely
        # the most common case (a one-page upload). Multi-page documents
        # always pass False here: their fields need the *full* merged
        # transcription, which doesn't exist until every page is done.
        combine_single_page_extraction = len(page_images) == 1

        routed_pages: List[Dict[str, Any]] = [None] * len(page_images)  # type: ignore[list-item]
        worker_count = min(MAX_CONCURRENT_PAGES_PER_DOCUMENT, len(page_images)) or 1
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_to_index = {
                executor.submit(
                    self._process_page, case_id, doc_id, index, page_image,
                    combine_single_page_extraction,
                ): index
                for index, page_image in enumerate(page_images)
            }
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    routed_pages[index] = future.result()
                except Exception as e:
                    # _process_page's own steps already catch their errors
                    # (see its docstring) — reaching here means something
                    # genuinely unexpected happened. Fail just this page
                    # rather than losing the whole document to it.
                    logger.exception(
                        "pipeline.page_processing_failed | document_id=%s page=%s",
                        doc_id, index + 1,
                    )
                    routed_pages[index] = {
                        "page_number": index + 1,
                        "original_text": f"[page processing failed: {e}]",
                        "source": "error",
                        "confidence": 0.0,
                        "has_handwriting": False,
                        "issues": [f"unhandled_exception: {e}"],
                        "structured_fields": None,
                    }

        merged_text = "\n\n".join(
            f"--- Page {p['page_number']} ---\n{p['original_text']}" for p in routed_pages
        )
        any_handwriting = any(p["has_handwriting"] for p in routed_pages)

        # Step 2: Structured field extraction.
        #
        # combine_single_page_extraction and this page's own routing already
        # got us fields in the same call as the transcription (see above) —
        # reuse them instead of making a second, redundant Gemini call from
        # text we already know. Falls through to the normal text-mode call
        # below if that combined call didn't happen (multi-page) or didn't
        # produce fields (the page stayed on OCR, never needed the VLM at
        # all — nothing to reuse) or failed outright (structured_fields is
        # None either way, so this check covers all three the same way).
        combined_fields = routed_pages[0].get("structured_fields") if combine_single_page_extraction else None

        if combined_fields is not None:
            result: Dict[str, Any] = {
                "success": True,
                "raw_output": None,
                "extracted": combined_fields,
                "model_used": "gemini-3.5-flash-lite",
                "error": None,
            }
            logger.info(
                "pipeline.structured_extraction | document_id=%s success=True elapsed=0.00s "
                "(combined with page transcription, no separate call)",
                doc_id,
            )
        else:
            # Uses a tag-stripped copy of merged_text, not merged_text itself: the
            # per-page transcription prompt (page_extraction_service.py) tags
            # signatures/stamps/checkboxes/handwritten notes with inline bracket
            # markup for reviewer display, which this text-only field-extraction
            # call was never designed to parse — feeding it raw could confuse
            # field parsing (e.g. a stray "[Stamp: ...]" inside a survey number).
            # merged_text itself (with tags) is still what gets stored/displayed
            # below (raw_ocr_text, extracted["full_text"]).
            fields_input_text = strip_annotation_tags(merged_text)
            extraction_started = time.monotonic()
            result = extract_structured_fields_from_text(fields_input_text)
            logger.info(
                "pipeline.structured_extraction | document_id=%s success=%s elapsed=%.2fs",
                doc_id, result["success"], time.monotonic() - extraction_started,
            )

        if not result["success"]:
            logger.error(
                "pipeline.structured_extraction_failed | document_id=%s error=%s",
                doc_id, result["error"],
            )
            self.doc_repo.update_status(doc_id, "flagged")
            return {
                "status": "failed",
                "case_id": case_id,
                "document_id": doc_id,
                "error": result["error"]
            }

        extracted = dict(result["extracted"])
        extracted["full_text"] = merged_text
        extracted["has_handwritten_content"] = any_handwriting
        raw_json = extracted
        validated_json = extracted

        # Run validation — includes handwriting override rule
        validation_result = validate_extraction(extracted)

        extraction_payload = {
            "document_id": doc_id,
            "raw_ocr_text": merged_text,
            "raw_json_output": raw_json,
            "validated_json_output": validated_json,
            "confidence": extracted.get("overall_confidence", "low"),
            "model_used": result["model_used"],
            "validation_errors": validation_result["errors"] + validation_result["warnings"],
            "needs_review": validation_result["needs_human_review"],
            "has_handwritten_content": any_handwriting
        }

        self.generic_repo.insert("extractions", extraction_payload)

        # Route based on validation instead of always going to under_review
        if validation_result["needs_human_review"]:
            self.doc_repo.update_status(doc_id, "flagged")
        else:
            self.doc_repo.update_status(doc_id, "llm_done")

        # Step 2b: Persist per-page text for search/page-view. Translation is
        # no longer automatic here — english_text starts null; the reviewer
        # triggers it on demand per document (POST /documents/{id}/translate,
        # see app/api/v1/documents.py) since not every document needs it and
        # it was previously running (and costing an API call) on every upload
        # whether wanted or not.
        # document_pages only has page_number/original_text/embedding
        # (/english_text) columns — routed_pages carries extra routing
        # telemetry (source, confidence, issues) that's already been logged
        # above, not persisted.
        page_rows = [{"page_number": p["page_number"], "original_text": p["original_text"]} for p in routed_pages]

        # Semantic search needs a vector per page — generated here (unlike
        # translation, this isn't optional/on-demand, since search should
        # just work without an extra manual step). A page whose embedding call
        # fails still gets indexed for exact-match search (embed_pages sets
        # embedding=None for it rather than dropping the page) — see
        # embedding_service.py.
        page_rows = embed_pages(page_rows)

        # Isolated in its own try/except (the comment above always intended
        # this — search/page-view being unavailable for a document shouldn't
        # also take down chain reconstruction, flagging, and case
        # finalization below, which don't depend on document_pages at all).
        try:
            self.doc_page_repo.bulk_create([
                {**page, "document_id": doc_id} for page in page_rows
            ])
        except Exception as e:
            logger.error("pipeline.document_pages_insert_failed | document_id=%s error=%s", doc_id, e)

        # Step 3: Populate Ownership Chain Records — isolated the same way as
        # the document_pages insert above: a schema/DB problem here shouldn't
        # also prevent flag analysis or case finalization below, neither of
        # which strictly depends on this insert having succeeded.
        chain = extracted.get("chain", [])
        try:
            for record in chain:
                self.generic_repo.insert("ownership_chain", {
                    "case_id": case_id,
                    "sequence_order": record.get("order"),
                    "owner_name": record.get("owner"),
                    "transaction_date": record.get("date"),
                    "transaction_type": record.get("type"),
                    "survey_number": record.get("survey"),
                    # Explicit, not just correctness — same stray-DEFAULT
                    # issue as reports.approved_by (see
                    # report_builder_service.py): the live ownership_chain
                    # table has a DEFAULT on document_id pointing at a UUID
                    # that no longer exists in documents, which fires (FK
                    # violation, breaking every insert) whenever this key is
                    # omitted instead of set to null. This record is
                    # case-level (a chain link can span/predate any single
                    # document), so null is also the semantically correct
                    # value here, not just a workaround.
                    "document_id": None,
                })
        except Exception as e:
            logger.error("pipeline.ownership_chain_insert_failed | document_id=%s error=%s", doc_id, e)

        # Step 4: Run Flag Analyzer Engine
        base_survey = extracted.get("survey_number")
        for record in chain:
            if base_survey and record.get("survey") != base_survey:
                try:
                    self.flag_repo.create_flag({
                        "case_id": case_id,
                        "flag_type": "Survey Number Mismatch",
                        "severity": "high",
                        "description": f"Chain link {record.get('order')} has survey {record.get('survey')} instead of {base_survey}",
                        "status": "raised"
                    })
                except Exception as e:
                    logger.error("pipeline.flag_create_failed | document_id=%s error=%s", doc_id, e)

        # Finalize
        self.case_repo.update_case(case_id, {"status": "review"})

        logger.info(
            "pipeline.document_completed | document_id=%s case_id=%s needs_review=%s elapsed=%.2fs",
            doc_id, case_id, validation_result["needs_human_review"],
            time.monotonic() - pipeline_started,
        )

        return {
            "status": "success",
            "case_id": case_id,
            "document_id": doc_id,
            "extracted": extracted,
            "needs_review": validation_result["needs_human_review"]
        }

    async def execute_batch(self, doc_ids: List[str]) -> None:
        """Runs execute_analysis_pipeline for multiple documents (one batch upload's
        worth) with bounded concurrency, instead of firing every extraction at once."""
        logger.info(
            "pipeline.batch_started | document_ids=%s concurrency=%s",
            doc_ids, MAX_CONCURRENT_EXTRACTIONS,
        )
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_EXTRACTIONS)

        async def _run_one(doc_id: str) -> None:
            async with semaphore:
                try:
                    await asyncio.to_thread(self.execute_analysis_pipeline, doc_id)
                except Exception:
                    # execute_analysis_pipeline already catches its own known
                    # failure points (rasterization, structured extraction)
                    # and returns {"status": "failed", ...} for them without
                    # raising. Reaching here means something unexpected blew
                    # up instead (e.g. a DB/storage call raising outright).
                    # Previously that was swallowed silently by
                    # asyncio.gather(..., return_exceptions=True) below —
                    # exactly why a document could vanish mid-batch with no
                    # error anywhere, indistinguishable from "still
                    # processing". Log the full traceback and make sure the
                    # document doesn't stay stuck in "processing" forever.
                    logger.exception("pipeline.document_crashed | document_id=%s", doc_id)
                    try:
                        self.doc_repo.update_status(doc_id, "flagged")
                    except Exception:
                        logger.exception(
                            "pipeline.document_crash_status_update_failed | document_id=%s", doc_id,
                        )

        await asyncio.gather(*(_run_one(doc_id) for doc_id in doc_ids), return_exceptions=True)
        logger.info("pipeline.batch_completed | document_ids=%s", doc_ids)

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
                "status": "draft",
                # See report_builder_service.py's get_or_create_report() for
                # why this must be explicit — the live table's approved_by
                # column has a stray DEFAULT pointing at a nonexistent user,
                # which fires (and breaks the insert) if this key is omitted.
                "approved_by": None,
            })
            self.case_repo.update_case(case_id, {"status": "review"})

        return {
            "case_id": case_id,
            "chain": chain_result,
            "flags_raised": len(risk_flags),
            "report_generated": draft_result["success"]
        }