# EasyHuntV2 — Audit vs SOP (steps 1–8)

Read-only audit, originally written before any of this round's changes. Scope: SOP steps 1–8 only (case creation through keyword search). Steps 9–11 (report format, generation, export) are parked per instruction — see [Report code (reference only)](#report-code-reference-only) below; nothing there was read in depth or changed.

Headline finding at the time: **the vendor role was already removed and SOP steps 1–8 were almost entirely implemented against real endpoints**, not mocked. The two real gaps found here (below) became Phases 1–2 of [ROADMAP.md](./ROADMAP.md); the dead-code inventory became Phase 3; the semantic-search discrepancy became Phase 4. **All four phases are now complete** — each gap/finding below is annotated with its resolution. This document is kept as the historical record of what justified the roadmap, not rewritten as if audited after the fact.

## SOP step-by-step status

| # | SOP step | Status | Implementation |
|---|---|---|---|
| 1 | Case creation | Done | `backend/app/api/v1/cases.py`, `app/services/case_service.py`; frontend `CaseCreationPage.tsx` → real `POST /cases` |
| 2 | Batch document upload | Done | `backend/app/api/v1/documents.py` (`POST /documents/upload`, `MAX_BATCH_SIZE=20`), `app/services/doc_service.py` (10MB/file, PDF/PNG/JPEG); frontend `BatchUploadPanel.tsx` (drag-drop, real XHR progress, status polling) |
| 3 | Image enhancement | Done | `backend/app/services/image_enhancement.py` — quality-gated deskew, `fastNlMeansDenoisingColored`, CLAHE contrast, unsharp mask; each step only runs if the page's own measured quality warrants it |
| 4 | OCR/VLM routing | Done | `backend/app/services/document_router.py::route_and_extract_page` — Tesseract first (`app/ocr/tesseract_provider.py`), routes to Gemini VLM if handwriting-ratio ≥ `ROUTER_HANDWRITING_THRESHOLD` (0.10) or OCR confidence < `OCR_FALLBACK_CONFIDENCE` (0.70) |
| 5 | Extraction (owners, dates, survey/plot, location, boundaries, transfer type, chain, **red flags**) | **Done (Phase 1)** | Structured fields + chain are extracted (`llm_extractor.py::EXTRACTION_PROMPT`). Disputes/litigation/encumbrances now extracted too, via a `red_flags` array added in Phase 1 — see [Gap 1](#gap-1--no-llm-driven-red-flag-legal-judgment-layer) |
| 6 | Handwriting confirmation (always flagged, fail-safe) | Done | `backend/app/services/validation.py:57-60` — `extracted.get("has_handwritten_content", True)`; missing key defaults `True`; `validate_extraction` sets `needs_human_review: True` unconditionally by design |
| 7 | Translation (original + English, cheap model) | Done | `backend/app/services/translation_service.py` — Google Cloud Translation v2 REST via `GOOGLE_TRANSLATE_API_KEY`, deliberately separate from the paid `GEMINI_API_KEY` used for extraction |
| 8 | Search (exact, doc+page, highlighted, editable) | **Done** | Exact `ILIKE` search over `document_pages.original_text`/`english_text` (`app/repositories/document_page_repo.py::search_by_case`), doc+page attribution, `HighlightedText.tsx` highlighting, inline page-text editing (`PATCH /documents/{id}/pages/{page_number}`). Semantic mode still exists but its UI toggle is hidden as of Phase 4 — see [semantic search note](#semantic-search-ahead-of-stated-scope) |

## Real gaps

### Gap 1 — no LLM-driven red-flag/legal-judgment layer — RESOLVED (Phase 1)

SOP §5 asks the extraction step to surface "disputes, litigation, encumbrances, and any other red flags affecting title." SOP §6 asks the LLM to operate with a property lawyer's judgment — specifically to recognize chain-of-title gaps, understand what a mutation entry or encumbrance means, and identify what legally counts as a red flag.

What existed at audit time:
- `backend/app/services/llm_extractor.py::EXTRACTION_PROMPT` and `STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT` both framed Gemini as "an expert at reading Indian property documents," which is document-transcription expertise, not legal judgment. Neither prompt's JSON schema had a field for disputes, litigation, or encumbrances. `document_type` included `encumbrance_certificate` only as a document *category*, not as a flag on content found inside any document.
- `backend/app/services/chain_service.py::ChainReconstructionService` and `app/services/risk_service.py::RiskFlaggingService` produced real `risk_flags` rows, but only from **structural** signals already present in the extracted chain: multiple distinct survey numbers ("Survey Number Conflict"), consecutive owner changes with no `transaction_type` ("Ownership Chain Gap"), and a ≤1-record chain ("Insufficient Ownership History"). A per-document "Survey Number Mismatch" check also existed inline in `pipeline_service.py`.
- None of this read a document's actual prose for a dispute clause, a pending-litigation notice, or an encumbrance narrative — it only reasoned over the already-extracted structured chain.

**Resolution (Phase 1, see [DECISIONS.md](./DECISIONS.md) D2):** both prompts in `llm_extractor.py` now include a `red_flags` array (taxonomy: `dispute`/`litigation`/`encumbrance`/`unregistered_transfer`/`name_mismatch`/`missing_link`/`other`) plus a lawyer-framing paragraph grounded in SOP §6. `pipeline_service.py` persists each entry into the existing `risk_flags` table tagged `source="llm"`, alongside the pre-existing structural checks (now tagged `source="structural"` for the same reason — see D3). **Not yet independently verified against a real document through the live Gemini API** — see DECISIONS.md's "Outstanding verification" section.

### Gap 2 — risk-flags UI is entirely unwired — RESOLVED (Phase 2)

The backend flags API was fully implemented and tested:
- `apiClient.flags.list`/`apiClient.flags.resolve` (frontend `services/api/hooks.ts`, via `useFlagsQuery`/`useResolveFlagMutation`) call real backend endpoints (`app/api/v1/flags.py`, `app/repositories/flag_repo.py`, 4 tests in `tests/test_flag_repo.py`).
- Grep confirmed **zero live components** called these hooks anywhere in `Frontend/src`.
- The one flags-shaped screen, `components/screens/RiskFlagsPanel.tsx`, was not imported by any route. It rendered a fully hardcoded 3-item array ("Open Judgment," "Tax Lien Hold," "Ownership Name Variant") with no-op Resolve/Dismiss/Note buttons.

Net effect at audit time: a lawyer using the live app had **no way to see any risk flag**, structural or otherwise, even though the backend already computed and stored them.

**Resolution (Phase 2):** `app/schemas/flags.py::FlagResponse` now includes `source`/`document_id` (previously silently stripped from every API response — a gap found while wiring the UI, not in the original audit). A new `Frontend/src/components/case/RiskFlagsPanel.tsx` calls the real API and is mounted in `CaseWorkspacePage.tsx`, showing a source badge (LLM vs structural) per flag with working Resolve/Dismiss actions. The old dead `components/screens/RiskFlagsPanel.tsx` was deleted in Phase 3 once this replaced it.

## Semantic search — ahead of stated scope — RESOLVED (Phase 4)

The SOP-8 brief asked for "exact match first, no fuzzy or semantic matching yet." The codebase already had a working semantic mode beyond that:
- `backend/app/services/search_service.py::SearchService.search_case(mode="semantic")` → `document_page_repo.py::search_by_case_semantic` → Postgres RPC `match_document_pages` (pgvector cosine distance, `migrations/0005_document_pages_embedding.sql`), embedding via `gemini-embedding-001`.
- Frontend `CaseSearchPanel.tsx` exposed this as a "Similar meaning" toggle alongside "Exact," with a similarity-% badge.
- Both modes are tested (`tests/test_search_service.py`, 16 tests).

**Resolution (Phase 4, see DECISIONS.md D5):** the "Similar meaning" toggle is removed from `CaseSearchPanel.tsx`; the search call now always passes `mode="exact"`. `search_service.py`'s semantic path, the `document_pages.embedding` column, and the RPC are untouched and dormant — re-enabling later needs only the UI toggle restored, nothing rebuilt.

## Dead / mock frontend code — RESOLVED (Phase 3)

All confirmed via grep at audit time to be unimported by any live route or component — none of it was reachable in the running app:

| File | What it was | Resolution |
|---|---|---|
| `Frontend/src/lib/mockApi.ts` | Fake `login()`/`signup()` with a `setTimeout`; zero imports | Deleted |
| `Frontend/src/lib/cases.ts` | `MOCK_CASES` array, mock `listCases()`/`createCase()`; also the **only remaining "vendor" reference in the repo** (`vendor_id` field, `"mock-vendor"` data, a stale "Requires role Vendor or Admin" comment); zero imports | Deleted — this also removed the last "vendor" trace in the repo |
| `Frontend/src/components/ui/FileDropzone.tsx` | Fully static fake upload widget (hardcoded fake files/progress, non-functional `<input>`); only referenced by a comment | Deleted |
| `Frontend/src/components/screens/RiskFlagsPanel.tsx` | Hardcoded flags array, no-op buttons — see Gap 2 above | Deleted, once superseded by Phase 2's real `components/case/RiskFlagsPanel.tsx` |
| `Frontend/src/components/ui/PdfDownloadButton.tsx` | Plain `<button>` with no `onClick`; only real consumer was `FullCaseDashboard.tsx` | Deleted; its usage in `FullCaseDashboard.tsx` was removed too (that file itself stays — still unrouted, out of this round's scope) |

Also flagged at audit time, not dead but cosmetically misleading — now fixed:
- `components/screens/HomePage.tsx` (routed at `/`) — had fabricated "live" stats ("226 Cases Checked," "2.3k Docs Indexed," "Entity Extraction 82%," "All systems operational") that were static JSX, not real data. **Fixed:** those numbers/status are removed; the "Review Pipeline" card now shows the four real pipeline stages (Intake/Extraction/Audit/Report) as a static, non-quantified description instead of fake live telemetry.
- `components/screens/LoginPage.tsx` — had decorative Google/Microsoft SSO buttons with no click handlers. **Fixed:** removed.
- `components/screens/UploadPage.tsx` — legacy standalone `/upload` route defaulting to a hardcoded demo case (`caseId: "PV-2408"`); already intentionally dropped from nav on 2026-08-21 per a comment in `AppNavigation.tsx`, because the real upload path is the per-case workspace (`CaseWorkspacePage.tsx`), which passes a real `caseId`. **Resolution:** deleted entirely, along with its `/upload` route — the user chose deletion over fixing the hardcoded defaults, since `CaseWorkspacePage.tsx` already covers this. The legacy `/cases/upload` redirect (which used to point at `/upload`) now points at `/cases` instead, so old bookmarks don't land on a dead route.
- `components/screens/FullCaseDashboard.tsx` — not routed anywhere; hardcoded KPI numbers, non-functional Filter/Grid buttons. **Not touched** — out of this round's explicit scope (only its `PdfDownloadButton` usage was removed, as a consequence of deleting that button component). Still unrouted, still has other hardcoded content; a candidate for a future cleanup pass if it ever becomes relevant.

## OCR language coverage

`backend/app/core/config.py:54` — `TESSERACT_LANGUAGES` defaults to `eng+hin+mar+tam+tel+kan` (English, Hindi, Marathi, Tamil, Telugu, Kannada — the last four intersected against whatever packs are actually installed, per `app/ocr/tesseract_provider.py::_resolve_languages`). This covers Devanagari (Hindi/Marathi) plus three major South Indian scripts, but not Gujarati, Bengali, Punjabi/Gurmukhi, Malayalam, or Odia.

**Decision (confirmed with user):** defer expansion — property documents can originate from any state, but adding packs speculatively isn't worth it until a real case surfaces an unsupported script. Documented here for future reference; not scheduled in this round's phased plan.

## Test suite

Project memory said "~26 tests, as of 2026-08-11" — was already stale at audit time (154 tests). **After all four phases, the suite has grown to 164 test functions across 14 files**:

| File | Tests | Covers |
|---|---|---|
| `test_auth_routes.py` | 3 | Self-registration removed, admin env-credential login, admin-creates-reviewer |
| `test_chain_service.py` | 21 | `ChainReconstructionService` + `RiskFlaggingService` (class-based); +6 since audit: source tagging (D3) and per-item insert isolation (Phase 1 follow-up hardening) |
| `test_document_processing.py` | 29 | `DocumentService` upload/authorize/delete + `PipelineService`; +6 since audit: LLM red-flag persistence/validation (Phase 1), extraction-insert and ownership_chain-insert isolation (follow-up hardening) |
| `test_document_router.py` | 9 | OCR-vs-VLM routing decisions |
| `test_documents_routes.py` | 19 | `/documents` API routes |
| `test_embedding_service.py` | 7 | Gemini embedding calls |
| `test_flag_repo.py` | 4 | Flag repository |
| `test_flags_schema.py` | 2 | **New in Phase 2** — `FlagResponse` serializes `source`/`document_id` |
| `test_image_enhancement.py` | 9 | OpenCV enhancement pipeline |
| `test_page_extraction.py` | 15 | Rasterization/DPI logic |
| `test_report_builder_service.py` | 16 | Manual report-builder excerpt CRUD |
| `test_report_pdf_builder.py` | 6 | PDF rendering incl. Devanagari font support |
| `test_search_service.py` | 16 | Snippet-building (exact + semantic) |
| `test_translation_service.py` | 8 | Google Translate wrapper |

There is also a standalone `backend/test_extraction.py` at the repo root, outside `tests/` — not counted above; worth checking separately whether it's a real test or a manual script before relying on it.

## Report code (reference only)

Per instruction: located and cross-referenced only, not read in depth, not modified, no recommendations.

- `backend/app/services/report_service.py` (`ReportGenerationService`) — only caller: `app/api/v1/reports.py`.
- `backend/app/services/report_draft_service.py` (`generate_draft_report`) — called from `pipeline_service.py:16,576` inside `finalize_case()` (line numbers as of end of Phase 1 — `pipeline_service.py` grew during this round, see below). Referenced (as explicitly *not* called) in a comment at `app/api/v1/report_builder.py:36`.
- `pipeline_service.py::finalize_case` (line 566) — called from `app/api/v1/cases.py:51` (`POST /cases/{case_id}/finalize`). **Note:** `app/api/v1/review.py:70` defines a separate, differently-named `finalize_case_review` route — a different function. Flagging this so the two aren't conflated in future work; neither was touched here.
- `backend/app/services/report_builder_service.py` (`ReportBuilderService.get_or_create_report`) — only router: `app/api/v1/report_builder.py`. Internally calls `report_pdf_builder.build_excerpt_report_pdf`.
- `backend/app/services/report_pdf_builder.py` (`build_excerpt_report_pdf`) — only caller: `report_builder_service.py`.
- Three coexisting report write-paths are called out directly in `backend/migrations/0003_report_excerpts.sql:4-9`: (1) `report_draft_service.py`'s LLM-draft flow, (2) `report_service.py`'s PDF-summary flow, (3) `report_builder_service.py`'s manual excerpt flow — distinguished by a `reports.report_type` column. Left exactly as-is; any future SOP-9–11 work should read this migration comment first.

## Other inconsistencies noted in passing

- `finalize_case` (pipeline) vs `finalize_case_review` (review route) — see above; same-ish name, different code, worth disambiguating before anyone touches either.
- The DB schema has no in-repo source of truth (no SQLAlchemy models, no Alembic, no Supabase CLI project) — every migration file's header comment says the base schema (`users`, `cases`, `documents`, `extractions`, `ownership_chain`, `reports`, `risk_flags`) lives only in the hosted Supabase dashboard. Any schema change needs to be applied there directly; the `backend/migrations/*.sql` files only capture incremental changes made since `document_pages` was introduced.
