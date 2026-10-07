# EasyHuntV2 — Decisions (SOP steps 1–8 realignment round)

## D1 — OCR engine: keep Tesseract, no re-evaluation

**Status:** Already decided and implemented before this round; documented here rather than re-litigated, since the original brief asked us not to assume an OCR engine.

**What's in place:** Tesseract (`app/ocr/tesseract_provider.py`), configured for `eng+hin+mar+tam+tel+kan` (`app/core/config.py:54`), with a confidence-based fallback to Gemini VLM for low-confidence or handwriting-heavy pages (`document_router.py`).

**Why this is reasonable to keep without a fresh bake-off:**
- It's free, local, and already handles Devanagari (Hindi, Marathi) plus three major South Indian scripts.
- It's already the confidence-based *first pass* in a hybrid pipeline — the expensive/better reader (Gemini VLM) is the fallback for exactly the cases where Tesseract is weakest (handwriting, low confidence), so Tesseract's known weaknesses on those cases are already mitigated by the architecture, not papered over.
- It's tested (`tests/test_document_router.py`, 9 tests) and working in production-shaped code, not a stub.

**What would justify revisiting this:** a case surfaces a document in a script Tesseract handles poorly even with the right language pack installed, or OCR-stage latency/accuracy becomes a measured problem. Neither has been observed. See D4 for the adjacent (but separate) language-pack-coverage question.

**Alternatives considered (for completeness, not because a switch is being made):** Google Cloud Vision / Azure Document Intelligence / AWS Textract — all stronger on messy/handwritten Indian-script text than Tesseract, but paid-per-page and would duplicate work the Gemini-VLM fallback already does for exactly those hard cases. PaddleOCR — free, decent multilingual support, but no material advantage over the already-integrated Tesseract+Gemini combination for this workload. Not pursued.

## D2 — Red-flag taxonomy and system-prompt strategy

**Decision:** Extend the existing `EXTRACTION_PROMPT`/`STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT` JSON contract with a `red_flags` array (six-type taxonomy: `dispute`, `litigation`, `encumbrance`, `unregistered_transfer`, `name_mismatch`, `missing_link`, `other`) and a short lawyer-framing paragraph grounded directly in SOP §6's own wording, rather than a second/separate LLM pass.

**Options considered:**
1. **Extend the existing extraction prompt (chosen).** One model call already reads the full document; asking it to also flag red flags in the same pass costs nothing extra in latency or API calls, and the flag can naturally reference the same transcription it's reading.
2. **Separate second-pass "legal review" prompt/call.** Would allow a more elaborate legal-reasoning prompt independent of the extraction schema, but doubles Gemini calls per document (cost, latency) for a benefit (prompt isolation) that doesn't clearly matter here — the six-type taxonomy is narrow enough to coexist with the existing extraction schema without confusing either.
3. **Fine-tuned/specialized legal model.** Out of scope — no indication of budget or data for this, and the SOP explicitly treats LLM output as a draft for lawyer verification, not a system that needs to be "more right" via fine-tuning; a well-scoped prompt is proportionate to that requirement.

**Why this taxonomy specifically:** four of the six categories are SOP's own words (dispute, litigation, encumbrance, "any other"). `unregistered_transfer`, `name_mismatch`, and `missing_link` were added because they're concrete, text-groundable signals that a property lawyer would actually flag, and they complement — rather than duplicate — the existing *structural* checks (`chain_service.py`'s survey-conflict/gap detection only look at the extracted chain array's own internal consistency, not at what the document's prose says). Tagging flags with `source: llm` vs `source: structural` (D3) keeps the two distinguishable instead of merging them into one undifferentiated list.

**Guardrail carried over from the SOP:** the prompt explicitly instructs "only flag what the text actually supports — do not infer a dispute that isn't stated," keeping this a draft signal, never an autonomous legal opinion, consistent with the SOP §6/§7 invariant.

## D3 — Persist LLM red flags into the existing `risk_flags` table, tagged by source

**Decision:** Add one `source text default 'structural'` column to `risk_flags` (migration `0006_risk_flags_source.sql`) rather than a new table or a new API surface.

**Why:** the existing `flags` API (`GET /flags`, `POST /flags/{id}/resolve`), its repository (`flag_repo.py`), and its (currently unwired) frontend hooks already model "a flag on a case with a severity, resolvable by a lawyer" — exactly what an LLM-derived red flag is. A new table/endpoint pair would duplicate that model for no benefit. The one thing genuinely new is *provenance* (did a human-legible structural rule produce this, or did the model read it out of the text) — one column captures that.

## D4 — OCR language-pack coverage: defer

**Decision:** Document the gap (Gujarati, Bengali, Punjabi/Gurmukhi, Malayalam, Odia not in `TESSERACT_LANGUAGES`) in AUDIT.md; don't add packs speculatively this round.

**Why:** adding a language pack has near-zero engineering cost (`_resolve_languages()` already intersects the configured list against whatever's installed, so it degrades gracefully — `app/ocr/tesseract_provider.py:36-52`), but there's no evidence yet that any real case needs one of the missing scripts. Confirmed with the user: expand when a real document surfaces the need, not ahead of it.

## D5 — Semantic search: hide, don't remove

**Decision:** Remove the "Similar meaning" toggle from `CaseSearchPanel.tsx` so only exact search is user-facing, matching the stated SOP-8 scope ("exact match first, no fuzzy or semantic matching yet"). Leave `search_service.py`'s semantic path, `document_pages.embedding`, and the `match_document_pages` RPC untouched and dormant.

**Options considered:**
1. **Hide the UI only (chosen).** Zero backend risk, zero loss of already-tested capability, and re-enabling it later (when the SOP scope is ready to include it) is a one-line UI change, not a rebuild.
2. **Leave it visible as-is.** Rejected — it visibly contradicts the stated SOP-8 scope today; a lawyer using semantic search now would be using a matching mode the SOP brief explicitly says isn't in scope yet.
3. **Remove it entirely** (delete the embedding column, RPC, service code, tests). Rejected — this is real, tested, working capability; deleting and later rebuilding it would be pure waste against a plausible near-future need (SOP itself doesn't rule out semantic search forever, just "not yet").

## D6 — Dead/mock frontend code: delete outright

**Decision:** Delete `lib/mockApi.ts`, `lib/cases.ts`, `FileDropzone.tsx`, `RiskFlagsPanel.tsx` (once Phase 2 supersedes it), `PdfDownloadButton.tsx`; fix or remove the fabricated stats in `HomePage.tsx` and the non-functional SSO buttons in `LoginPage.tsx`; resolve `UploadPage.tsx`'s hardcoded demo case.

**Why:** all confirmed via grep to be unimported by any live route (AUDIT.md has the full list) — deleting them carries no functional risk, and `lib/cases.ts` in particular is the last remaining trace of the already-removed "vendor" role, so removing it also finishes that earlier cleanup. Everything is recoverable from git history if a future report-builder-adjacent screen (parked, SOP 9–11) turns out to want a similar component.

## D7 — Defensive-insert hardening: isolate every risk_flags/chain insert, individually

**Decision:** three insert sites, found while investigating a question about whether a pre-migration flag row could be mislabeled, were made defensive to match the pattern already used elsewhere in `pipeline_service.py` (log-and-continue per item, not one try/except around a whole batch):
1. `risk_service.py::run_case_level_checks` — its three `create_flag` calls (survey conflict, chain gap, insufficient history) were entirely unguarded, and `finalize_case()` calls this method with no try/except of its own. A single failed insert (e.g. a schema mismatch) would have raised uncaught, losing the other flags from that run *and* crashing case finalization outright. Now each is wrapped individually.
2. `pipeline_service.py`'s `ownership_chain` insert loop wrapped the *entire loop* in one try/except, so one bad record silently dropped every chain record after it. Changed to per-record isolation, matching the flag-insert loops that were already written this way.
3. `pipeline_service.py`'s `extractions` insert (the primary record the whole per-document pipeline exists to produce) was entirely unguarded. Reached via a FastAPI `BackgroundTask` (`POST /documents/{id}/process`), an uncaught exception there doesn't surface as an HTTP error at all — the document was left silently stuck "processing" forever, the same failure mode `execute_batch`'s own wrapper exists to prevent for the batch-upload path. Now wrapped: on failure it logs, marks the document `flagged`, and returns `{"status": "failed", ...}`, matching the existing "structured extraction failed" pattern, and skips downstream steps (pages/chain/flags) that would otherwise reference a document with nothing backing its status.

**Options considered (site 3 specifically, presented to the user):** leave it loud-fail (arguably correct if risk analysis genuinely can't complete) vs. wrap it defensively (consistent with every other insert in this pipeline). Chosen: wrap defensively — consistency with the rest of the file, and a stuck-forever silent failure is worse than a loud one, not better.

**Why this wasn't caught by the original Phase 1 review:** the three sites above predate this round's changes (or were touched incidentally by D3's `source` tagging) and weren't part of the planned Phase 1 file list — they surfaced from a direct question about the blast radius of adding an unmigrated column to existing insert calls, not from the original audit.

## D9 — Optional Celery/Redis document queue, off by default

**Decision:** Add Celery with Redis as an *optional* way to run the document pipeline (`CELERY_ENABLED`, default `false`; the Docker Compose stack turns it on). With it off, nothing changes: uploads run through the existing in-process `PipelineService.execute_batch`, and the API and test suite start without celery being importable.

**Why:** The in-process path already runs three documents at once (each with four concurrent pages), so the queue is not about basic parallelism. It adds durability (queued work survives an API restart or deploy), horizontal scaling by adding workers, and keeping long OCR/VLM work out of the API process. That is worth having for a hosted deployment, but it is a new service to run, so it is opt-in.

**How it relates to `execute_batch`:** both call the same `execute_analysis_pipeline` per document. `app/services/document_dispatch.py` chooses exactly one per upload (and per `/documents/{id}/process`), so there are never two competing batch paths. A worker's `CELERY_WORKER_CONCURRENCY` (default 3, hard-capped at 6) replaces `execute_batch`'s semaphore.

**Failure behaviour (decided by the team lead):** if the broker is unreachable (or celery is not installed) when enqueuing, the documents fall back to the in-process path rather than failing, with an error-level `QUEUE_UNAVAILABLE_*` log on every occurrence and a `processing_mode`/`warning` in the API response that the upload panel shows. Only if not even the fallback is possible is the document marked `flagged` (and `/process` returns 503). A document is never left in `processing` with nothing working on it.

**Rate limits:** Gemini calls already retry three times inside the SDK. If a document still fails because Gemini rate-limited it (429/`RESOURCE_EXHAUSTED`), the pipeline's failure result carries an additive `rate_limited` flag and the task retries with exponential backoff and jitter (30 s base, up to 5 retries). Other unexpected errors retry twice. The flag only labels failures: extraction output on success, in-process failure handling, and the `has_handwritten_content` missing-means-`True` default are unchanged (tests in `test_rate_limit.py`).

**Known limits, deliberately left alone:** a single *page* that Gemini rate-limits still degrades inside the router as before (changing that would change extraction output); only document-level structured-extraction rate limits are retried. A retry after a crash that happened after the `extractions` row was written is skipped by the existing `already_processed` guard, so that document stays half-processed until it is reprocessed. The fallback state is shown in the upload response and panel, not stored per document, because that would need a new column.

**Why not the alternatives:** a bigger in-process semaphore gives none of the durability; a hosted queue service (SQS, Cloud Tasks) would tie us to one cloud before that decision is made. Celery on Redis runs identically on a laptop and in Docker.

## Outstanding verification (not yet done)

- ~~Migration `backend/migrations/0006_risk_flags_source.sql` has not been applied~~ — **confirmed applied to the live Supabase project.**
- **Phase 1's red-flag extraction (the `red_flags` field added to `EXTRACTION_PROMPT`/`STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT`) has only been verified against fakes in `pytest` — not against a real document through the live Gemini API.** The taxonomy, the lawyer-framing paragraph, and the defensive parsing (`_iter_valid_red_flags`) are all unit-tested, but nobody has confirmed the model actually produces sensible, well-formed `red_flags` entries for a real dispute/encumbrance clause yet. Now that the migration is applied, verify by uploading a real test document (see the Phase 1 hand-verification steps) — **still outstanding**, deferred by the user ("will do it later").
- **Hand verification of Phases 2–4 is also still outstanding.** All four phases have automated test coverage (164 passing) and clean frontend builds, but nobody has clicked through the actual running app yet — risk-flags rendering with real data (Phase 2), the deleted/fixed dead-code screens (Phase 3), and exact-only search behavior (Phase 4) are all unverified by hand. See each phase's "Manual verification" column in ROADMAP.md.
- ~~Open, not yet decided: unrecognized/malformed `red_flags[].severity` default~~ — **decided**: defaults to `"high"`, not `"medium"` (`pipeline_service.py::_iter_valid_red_flags`). Same fail-toward-more-scrutiny reasoning as `has_handwritten_content`'s fail-safe `True` default — a lawyer glancing at one extra high-severity flag costs less than a genuinely serious one being buried. Also decided: the `red_flags` taxonomy stays three levels (`high`/`medium`/`low`), no `"critical"` tier — `_VALID_RED_FLAG_SEVERITIES` in `pipeline_service.py` already only recognized these three, so no code change was needed there beyond the default. Note this is scoped to LLM red flags only: `app/schemas/flags.py::FlagSeverityEnum` (used by the pre-existing manual flag-raising endpoint, `POST /flags/{case_id}`) still allows `"critical"` — that's a separate, out-of-scope feature, not touched.
