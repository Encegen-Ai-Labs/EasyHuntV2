# EasyHuntV2 — System design: current state + delta (SOP steps 1–8)

Companion to [ARCHITECTURE.md](./ARCHITECTURE.md). Documents the parts of the system relevant to SOP steps 1–8 as they exist, and specifies the delta for Phase 1 (red-flag layer) and Phase 2 (risk-flags UI) precisely enough to implement from. Phases 3–4 are cleanup/UI-hiding and don't change the system design (see ROADMAP.md).

## DB schema

No in-repo schema source of truth — base tables (`users`, `cases`, `documents`, `extractions`, `ownership_chain`, `reports`, `risk_flags`) live only in the hosted Supabase dashboard. Tracked migrations (`backend/migrations/*.sql`) only capture incremental changes:

| Migration | Change |
|---|---|
| `0001_document_pages.sql` | `document_pages(id, document_id FK, page_number, original_text, created_at)`, unique `(document_id, page_number)` |
| `0002_document_pages_english_text.sql` | `document_pages.english_text` |
| `0003_report_excerpts.sql` | `reports.report_type`, `report_excerpts` table (out of scope here — see AUDIT.md) |
| `0004_extractions_review_notes.sql` | `extractions.review_notes` |
| `0005_document_pages_embedding.sql` | `document_pages.embedding vector(768)`, ivfflat index, `match_document_pages()` RPC |

### Delta — Phase 1

`risk_flags` already exists (used by `risk_service.py`, `flag_repo.py`, tested in `test_flag_repo.py`) with at least `case_id`, a title/description, and `severity`. Add one column via a new numbered migration:

```sql
-- backend/migrations/0006_risk_flags_source.sql
alter table risk_flags add column source text not null default 'structural';
-- values: 'structural' (chain_service.py / risk_service.py, existing) | 'llm' (new, Phase 1)
```

No other schema changes needed — the new red-flag data comes back as part of the existing `extractions` JSON blob (new keys on an already-JSON field), not a new table.

## Extraction routing (current — unchanged by this round)

`document_router.py::route_and_extract_page`, per page:
1. Run Tesseract (`app/ocr/tesseract_provider.py`, langs = `TESSERACT_LANGUAGES` ∩ installed packs).
2. Compute handwriting ratio from per-word OCR confidence (words <60 confidence flagged `is_handwritten` — a proxy, not a real handwriting classifier — `app/ocr/provider.py:28-35`).
3. If handwriting ratio ≥ `ROUTER_HANDWRITING_THRESHOLD` (0.10) OR OCR mean confidence < `OCR_FALLBACK_CONFIDENCE` (0.70) OR no OCR engine available → route to Gemini VLM for that page instead.
4. Page's `original_text`, `has_handwriting`, and routing source are returned; `has_handwriting` per page is OR'd across all pages into the document-level `has_handwritten_content` (`pipeline_service.py:236,295,311`), which `validation.py` defaults to `True` if ever missing.

No change proposed. `EXTRACTION_PROMPT`'s own self-reported `has_handwritten_content` (line 56) is used by the whole-document path only; the per-page routed pipeline's OCR-confidence-derived value is authoritative in the primary flow, per an explicit comment in `llm_extractor.py:82-90`. This is documented, not a discrepancy to fix.

## Delta — Phase 1: red-flag / legal-judgment extraction

### Extraction schema change

Add to `EXTRACTION_PROMPT` and `STRUCTURED_EXTRACTION_FROM_TEXT_PROMPT` in `backend/app/services/llm_extractor.py`:

```json
"red_flags": [
  {
    "type": "dispute | litigation | encumbrance | unregistered_transfer | name_mismatch | missing_link | other",
    "description": "one to two sentences, grounded in the document's actual text — quote or closely paraphrase the relevant clause",
    "severity": "high | medium | low",
    "source_text": "the specific phrase/clause that triggered this flag, verbatim if possible"
  }
]
```

Taxonomy rationale (six types, matching SOP §5's own list plus the two structural categories already in use, so `source: llm` and `source: structural` flags read consistently side by side):
- `dispute` / `litigation` — SOP's own wording ("disputes, litigation").
- `encumbrance` — SOP's own wording; distinct from the `encumbrance_certificate` *document type* — this fires when encumbrance language appears in the body of *any* document, not just when the document itself is an EC.
- `unregistered_transfer` — a transfer described in the text with no registration/mutation evidence; a common real-world red flag not literally named in the SOP but implied by "chain of ownership... who held it, in what order" needing to be verifiable.
- `name_mismatch` — owner name spelled/rendered inconsistently across documents in the same case; complements the existing structural "Survey Number Conflict" check.
- `missing_link` — the document's own text references a prior transfer or owner not otherwise evidenced anywhere in the case (distinct from the existing structural "Ownership Chain Gap," which only looks at gaps *within* the extracted chain array, not at prose references to missing predecessor documents).
- `other` — catch-all, per SOP's "any other red flags."

### System-prompt framing

Add a short paragraph to both prompts, grounded directly in SOP §6's own language (not invented legal doctrine):

> When reading this document, also watch for anything that would concern a property lawyer verifying title: language suggesting an ongoing dispute or litigation, any encumbrance (mortgage, lien, charge) mentioned anywhere in the text, a transfer described but not evidenced by registration/mutation, an owner name that doesn't match how it appears elsewhere, or any reference to a prior transaction not otherwise documented in this file. Only flag what the text actually supports — do not infer a dispute that isn't stated.

This is intentionally narrow: the LLM flags what's *in the document's own text*, not speculative legal analysis. It stays a draft signal for the lawyer, consistent with the SOP's "assists judgment, does not replace it" principle — never a legal opinion.

### Persistence

`pipeline_service.py`, after structured extraction: for each entry in `extracted["red_flags"]`, insert a `risk_flags` row with `source="llm"`, alongside the existing structural pass's `source="structural"` rows. Both share the same table/API — no new endpoints. `RiskFlaggingService` (Phase 1 touches this file only to add the `source` tag on its existing inserts, not its logic) and the new LLM-flag persistence can live in `pipeline_service.py` directly (small, single call site) rather than a new service file, to avoid an unnecessary abstraction for ~10 lines of insert logic.

### API — no change

`GET /flags` (list, filterable by case), `POST /flags/{id}/resolve` already exist (`app/api/v1/flags.py`) and already return/accept whatever columns the table has — the new `source` column flows through automatically. Phase 1 does not touch this file.

## Delta — Phase 2: risk-flags UI

No backend change. New frontend component (name/location TBD at implementation time, e.g. `components/case/RiskFlagsPanel.tsx` — replacing, not extending, the dead one of the same name) that:
- Calls `useFlagsQuery(caseId)` (already defined in `services/api/hooks.ts`, currently unused).
- Renders each flag with its `source` badge (LLM vs structural) so a lawyer can tell a text-derived red flag from a chain-structure check at a glance.
- Calls `useResolveFlagMutation` on resolve/dismiss (already defined, currently unused).
- Mounts inside `CaseWorkspacePage.tsx` alongside the existing search/upload/review panels.

## Page-level tracking, translation, search (current — unchanged)

All already implemented and covered by tests; see AUDIT.md for the full file list. No design change in this round. Phase 4 only hides the semantic-search UI toggle (`CaseSearchPanel.tsx`) — the `search_service.py`/`document_page_repo.py`/RPC layer is untouched.
