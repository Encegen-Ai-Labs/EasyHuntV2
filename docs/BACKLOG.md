# Backlog

Things deliberately not done yet, each with enough context to pick up later. Not a commitment or a priority order. Move an item into ROADMAP.md (and DECISIONS.md if it needs a decision) when it is scheduled.

## Waiting on information

- **Survey number removal.** The case form still asks for a survey number. Plan: make `cases.survey_number` nullable and store `null`, not `""`; make `CaseResponse.survey_number` optional; drop or fill from extractions the "Survey Number" rows in `report_pdf_builder.py` and `report_service.py`. Nothing in chain, risk or pipeline checks reads the case-level value. Blocked on checking the Supabase column's `NOT NULL`/`UNIQUE` constraints.
- **Embedding backfill.** Pages processed before migration 0005 have no embedding and never appear in similar results. Blocked on the live counts of `document_pages` with and without `embedding` (and on confirming 0005 is applied).
- **Similarity threshold.** `SEARCH_MIN_SIMILARITY` is 0.30 and uncalibrated. Tune it on real Marathi/Hindi cases, and check quality of English queries against Marathi pages (only `original_text` is embedded).

## Cleanup found during the PR #27 review

- The dashboard fabricates values: `normalizeCase` in `Frontend/src/services/api/client.ts` defaults `risk` to "Medium", `priority` to "High", `confidence` to 85 and the assignee to "System Reviewer", because the backend sends none of them. The Risk column is therefore fiction. Remove the columns or compute real values.
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
- The "two pollers on the upload page" item above is fixed: the upload panel no longer polls.

## From the production-safety pass (D11)

- **Rotate the Translation API key.** It was shown on screen and stored in one page's text (scrubbed on 2026-10-12), so treat it as exposed. Create a Cloud Translation key if Google Translation is wanted; otherwise leave `GOOGLE_TRANSLATE_API_KEY` empty and translation runs on Gemini.
- **Check the price settings** (`LLM_PRICE_*`) against Google's price list for the model in use, and set `DAILY_LLM_BUDGET_USD` and a Google Cloud billing budget alert.
- **Set `SENTRY_DSN`** and an uptime monitor on `/health/ready`; set a real `APP_JWT_SECRET` (changing it signs everyone out once).
- **ESLint reports 7 errors** (the React `set-state-in-effect` rule, in ThemeToggle, AuthContext, UserManagementPage, ReportBuilderPage, CaseSearchPage, UsagePage). CI shows lint as report-only until they are fixed; then make it blocking.
- **Add ruff configuration** for the backend, then make the lint step blocking.
- **Login token in `localStorage`.** Move to an httpOnly cookie. Add a Content-Security-Policy once the production addresses are known.
- **Migrations are applied by hand.** Needs the base schema in the repo before a CI migration check or automatic migration step (see PRODUCTION_PLAN section 5).
- **Supabase advisor warnings:** set a fixed `search_path` on `match_document_pages` and `extraction_corrections_no_update`; move the `vector` extension out of `public`.
- **Server set-up for CD** (staging and production hosts, deploy keys, branch protection): steps in CICD.md.
- **Frontend error tracking** (`@sentry/nextjs`) is not added; only the backend reports to Sentry.

- **Drop the unused embedding pieces from the database** in a new migration marked `-- destructive-ok`: `document_pages.embedding` (and its index), the `match_document_pages` function, and move the `vector` extension out of `public`. The code no longer uses them.
