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
