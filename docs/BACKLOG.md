# Backlog

Things deliberately not done yet, each with enough context to pick up later. Not a commitment or a priority order. Move an item into ROADMAP.md (and DECISIONS.md if it needs a decision) when it is scheduled.

## Revisit when we design the export step

### Stream the report PDF through the API instead of a signed URL

Today `POST /cases/{id}/report-builder/export` uploads the PDF to Supabase Storage and returns a signed URL that the browser opens in a new tab, so a bearer token for the file ends up in the address bar and browser history.

Intern PR #27 (commit `963e415`) changed this: the service returns the PDF bytes, the endpoint streams them with `Content-Disposition: attachment`, `Cache-Control: private, no-store` and `X-Content-Type-Options: nosniff`, and the frontend downloads a Blob. The code is sound and its tests passed, but it also changes the API contract (JSON to binary, `ReportExportResponse` removed) and was not part of the requested work, so it was left out of the merge.

To revisit: take it when the export step is designed, as its own change, together with any bank-template export format. Files in that commit: `backend/app/api/v1/report_builder.py`, `backend/app/services/report_builder_service.py`, `backend/app/schemas/report_builder.py`, `backend/tests/test_report_builder_service.py`, `Frontend/src/components/screens/ReportBuilderPage.tsx`, and the export parts of `Frontend/src/services/api/client.ts`. Signed URLs already issued stay valid until they expire; streaming does not revoke them.

## Waiting on information

- **Survey number removal.** The case form still asks for a survey number. Plan: make `cases.survey_number` nullable and store `null`, not `""`; make `CaseResponse.survey_number` optional; drop or fill from extractions the "Survey Number" rows in `report_pdf_builder.py` and `report_service.py`. Nothing in chain, risk or pipeline checks reads the case-level value. Blocked on checking the Supabase column's `NOT NULL`/`UNIQUE` constraints.
- **Embedding backfill.** Pages processed before migration 0005 have no embedding and never appear in similar results. Blocked on the live counts of `document_pages` with and without `embedding` (and on confirming 0005 is applied).
- **Similarity threshold.** `SEARCH_MIN_SIMILARITY` is 0.30 and uncalibrated. Tune it on real Marathi/Hindi cases, and check quality of English queries against Marathi pages (only `original_text` is embedded).

## Cleanup found during the PR #27 review

- The dashboard fabricates values: `normalizeCase` in `Frontend/src/services/api/client.ts` defaults `risk` to "Medium", `priority` to "High", `confidence` to 85 and the assignee to "System Reviewer", because the backend sends none of them. The Risk column is therefore fiction. Remove the columns or compute real values.
- `Frontend/src/components/screens/FullCaseDashboard.tsx` is imported nowhere and still has hard-coded KPIs. Delete it (D6).
- "Flagged" means two things: a document status (`flagged`, shown in the documents list) and case-level `risk_flags` rows (`RiskFlagsPanel`). Consider relabelling the document status (the review toast already says "flagged for correction").
- Upload page runs two pollers (the batch panel every 4 s and the documents list every 3 s). One source would do. A document stuck in `processing` is polled forever.
- Admin can only create Reviewer accounts (`POST /admin/reviewers` pins the role). Creating other admins or roles is new work. The create response also echoes the plaintext password back.

## Queue hardening (see D9)

- Persist the "processed in-process because the queue was down" state per document. Needs a new column; today it is shown only in the upload response and panel, and in the API log.
- A rate-limited *page* (not the document-level extraction) still degrades inside the router as before. Retrying it would change extraction output, so it needs its own decision.
- A retry after a crash that happened after the `extractions` row was written is skipped by the `already_processed` guard, leaving the document half-processed. Make reprocessing resumable or clear partial rows first.
- Live Docker worker test (see `docs/SETUP.md`, "Verify a real worker"); only the image build and an in-image import check have been done.


## Production readiness (see docs/PRODUCTION_PLAN.md)

Found while writing the production plan; the plan schedules them, this list keeps them from being lost.

- **Base schema is not in the repo.** `users`, `cases`, `documents`, `extractions`, `risk_flags`, `reports` and the storage buckets were created by hand; migrations 0001-0009 only add to them. Needs a `0000_baseline.sql` dumped from the live project (plan, section 5).
- **Same-name uploads overwrite each other in storage.** `doc_service.upload_file` stores at `cases/{case_id}/{file_name}` with `x-upsert: true`, so two files with one name in a case share one storage object while both rows survive.
- **CORS is `*` with credentials** in `app/main.py`; lock to the frontend origin.
- **App JWTs are signed with the Supabase JWT secret.** Use a separate `APP_JWT_SECRET`.
- **`/health` is shallow** and the worker has no health check; add a readiness endpoint (Supabase, Redis) and `celery inspect ping`.
- **No Gemini usage/cost tracking** and logs are plain text; add a usage wrapper and `llm_usage` table, structured logs.
- **No audit log** of who viewed, edited or exported which client record.
- **Redis broker settings:** enable AOF persistence and a password; set `visibility_timeout` above `task_time_limit` (both are 1 h now, so a long task can be redelivered while running).
- **Stuck-document sweeper:** nothing flags a document left in `processing` after a hard failure.
- **No page cap** in `rasterize_pages` for PDFs.
- **`requirements.txt` is unpinned** and carries test-only packages (`pytest`, `httpx`) into the runtime image; no backend linter; no frontend Dockerfile.
- **Does `delete_document` remove everything derived?** (enhanced page images, embeddings, `extraction_cache`, `extraction_corrections`, report excerpts). Unverified; matters for deletion on request.
- **Word and Excel upload** (LibreOffice headless conversion to PDF ahead of `rasterize_pages`; design in plan section 9).
- **Gemini and Cloud Translation process outside India.** Whether that is acceptable to the banks is an open question; the alternative is Vertex AI in Mumbai.

## From the attorney-flow rebuild (D10)

- **Store report drafts on the server.** Edited drafts are kept in the browser only (localStorage), so they do not follow a lawyer to another computer. Needs a `report_drafts` table (case_id, format_id, content jsonb, updated_by, updated_at; unique on case_id + format_id) and a migration.
- **Verify bank PDF export in the Docker image** (LibreOffice was added to the Dockerfile but never built or run). Also check Marathi text renders in a converted PDF.
- **Bank prefill depends on what the documents say.** A Gemini call fills the factual fields (D10 addendum); fields the documents do not state stay empty. Judge quality on fuller documents (sale deed, 7/12) than the short extracts tried so far.
- **Upload your own bank format** (UI placeholder only).
- **Delete `Frontend/src/components/search/CaseSearchPanel.tsx`** (no longer used; superseded by the Search & select page). The old `POST .../report-builder/export` endpoint and `report_pdf_builder.build_excerpt_report_pdf` are also unused by the UI now.
- The "two pollers on the upload page" item above is fixed: the upload panel no longer polls.
