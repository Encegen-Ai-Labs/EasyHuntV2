# Review of intern PR #27

**Author:** Aditya2OO4 (built with Copilot, outside our context)
**Branch:** `pull/27/head`, fetched locally as `pr-27-intern`. Nothing merged, no code changed.
**Shape:** one commit (`963e415`) on top of current `origin/dev` (`2a95a91`, which already contains PR #26). 42 files, +895 / −324.
**Our branch (`pipeline-search-report-builder-rewrite`):** only adds the bank-template work on top of dev. `git merge-tree` merges cleanly and the two sides touch no common files.

## What I verified and what I didn't

| Check | Result |
|---|---|
| Full backend suite on his branch | **166 passed**, but only after installing `celery[redis]` (into a scratch dir). On our current venv the suite can't even be collected (see 7). |
| `tsc --noEmit` on his frontend | Clean |
| ESLint, `next build`, Docker build, a live Celery worker, any browser walkthrough | **Not run.** His own notes say the same for Docker and the browser. |
| His `SESSION_CHANGES.md` claims | Mostly accurate, but it overstates test coverage (see "Low quality / risky"). |

## Per-item status against his checklist

| # | Item | Verdict | Where |
|---|---|---|---|
| 1 | Rename PropVerify v2.0 → EasyHuntV2 (frontend) | **Done** | `layout.tsx`, `AppNavigation.tsx`, `HomePage.tsx` (the "PropVerify Intelligence v2.0" badge), `LoginPage.tsx`, `CaseCreationPage.tsx`, `AuthContext.tsx`, `DashboardPage.tsx` (CSV filename). Only `propverify_*` localStorage keys remain; leaving them is correct, since renaming would log everyone out. |
| 2 | Landing page content and alignment | **Content done; alignment unverified** | `HomePage.tsx` rewritten onto theme tokens, with the glassmorphism and 3D-tilt hero and the fake "Risk Status: Clear & Ready" overlay removed. I haven't seen it rendered. Hard-coded indigo/purple/emerald icon tiles remain. |
| 3 | Remove Continue with Google/Microsoft on login | **No-op, already done** | There are no such buttons on `dev` (grep for google/microsoft/sso finds only `next/font/google`). They went in Phase 3 / D6. His own notes concede this. |
| 4 | Remove critical risk flag from case dashboard | **Done** | `DashboardPage.tsx`: KPI card and computation removed, grid 4→3 cols. See note below. |
| 5 | Remove case wizard on case creation | **Done, but check intent** | The only "wizard" in the code was a `Case Wizard` badge in `CaseCreationPage.tsx`. It's gone. There was never a multi-step wizard, so if you meant something larger, he hasn't touched it. |
| 6 | Remove survey number field | **Implemented; backend half needs changes** | Frontend field, validation, API types, schema (`Optional`), test. Dependency analysis below. |
| 7 | Parallel uploads: Celery + Redis + Docker | **Implemented, untested live, has real defects** | `tasks/`, `docker-compose.yml`, `Dockerfile`, `documents.py`, `config.py`. See below. |
| 8 | Button to review workspace after processing | **Done** | `BatchUploadPanel.tsx`: "Open review workspace" when every tracked doc is terminal. Target `/review?caseId=` matches the existing nav. |
| 9 | Documents list stale until refresh; two "flagged" sections | **List fix done; "two sections" is half-answered** | `DocumentList.tsx`, `BatchUploadPanel.tsx`. See below. |
| 10 | Similar search doesn't highlight matched words | **Partial, and part of it conflicts with D5** | `HighlightedText.tsx`, `CaseSearchPanel.tsx`. See below. |
| 11 | Select text in the review workspace | **Done** | `ReviewPage.tsx` reuses the existing `SelectableText` (already used by search) on the read-only original and English page text, and posts via `reportBuilder.addExcerpt`. The backend does no substring validation on `excerpt_text`, so selecting from the English side is fine. |
| 12 | Admin can create other accounts | **Not touched; already exists** | See below. |

**Item 4 note.** The backend never sends `risk` on a case. `normalizeCase` in `client.ts` defaults it to `"Medium"`, so "Critical" never occurred and the card was always 0. Removing it is right. The same defaults also fabricate `priority: "High"`, `confidence: 85` and the assignee "System Reviewer". The dashboard Risk column is therefore still fiction. That's a separate cleanup he didn't touch. Also, `FullCaseDashboard.tsx` is imported nowhere and still has hard-coded KPIs ("24 / 06 / 03 / 11"). By D6 it should be deleted.

## Item 6: what depends on the case-level `survey_number`

Safe to remove from intake. Nothing makes a decision from it:

| Consumer | Reads case-level value? | Effect of `""` / absent |
|---|---|---|
| `chain_service.py` (survey-conflict detection) | No, uses `survey_number` on chain records from extractions | none |
| `risk_service.py` ("Survey Number Conflict") | No, consumes `chain_service` output | none |
| `pipeline_service.py` ("Survey Number Mismatch") | No, `extracted.get("survey_number")`, the document's own value | none |
| `report_draft_service.py` | No, chain records | none |
| `report_pdf_builder.py` (report-builder PDF) | **Yes**, prints `case.get("survey_number") or "N/A"` | row shows "N/A" |
| `report_service.py` (legacy report, `/reports`) | **Yes**, `case_obj["survey_number"]` | prints a blank "Survey Number Ref:" |
| Bank-template manifests (`*.fields.json`) | No case-level source; the survey-like fields (gat/survey chains) are `extracted` | none |
| Frontend | Only the workspace header, which he removed | none |

Open problems with his backend half:
- `cases.py` stores `payload.survey_number or ""`. The `cases` schema lives in the Supabase dashboard, not in the repo, so I can't confirm the column's `NOT NULL` or any `UNIQUE` constraint. **If it is unique, the second case with `""` fails.** Check it in Supabase before taking this.
- The cleaner fix is a migration (`0007`) making the column nullable, passing `None`, and making `CaseResponse.survey_number` `Optional`. Whether to do that or keep the `""` sentinel is your call.
- The two PDF rows should be dropped (or filled from extractions) rather than printing "N/A" or blank.

## Item 7: Celery / Redis / Docker

The design is sound: one task per document, late ack, two retries, `flagged` on final failure, status read from the DB, and the old FastAPI background-task path kept as the default (`CELERY_ENABLED=false`). Defects:

1. **Celery becomes a hard dependency even when disabled.** `documents.py` imports `app.tasks.document_tasks` at module top, which imports `celery`. On our current venv `import app.api.v1.documents` raises `ModuleNotFoundError` (verified), so the API can't start until requirements are reinstalled. This contradicts "optional". Fix: import lazily inside the `CELERY_ENABLED` branch.
2. `/documents/{id}/process` calls `.delay()` with no try/except, unlike the upload path. A broker outage there is a 500 and the document status is untouched.
3. Retries re-run the whole pipeline. The existing `already_processed` guard keys on an `extractions` row, so a crash after the extraction insert but before pages/chain/flags leaves the document half-processed and a retry skips the rest.
4. A `result_backend` is configured but nothing reads task results, since status comes from the DB. It's extra Redis state that can be dropped.
5. Throughput ceiling is workers × concurrency (3) × 4 pages, about 12 simultaneous Gemini calls per worker. There's no rate-limit handling.
6. The container runs as root. The image is unpinned (`celery[redis]>=5.4.0`).
7. **Untested:** the enqueue-failure branch and the `/process` branch have no tests, and no live worker run was done.
8. Adds new infrastructure (Redis plus a worker process) with **no DECISIONS.md entry**. His only DECISIONS edit is D8 (search).

## Item 9: stale documents list, and "two flagged sections"

- **Root cause confirmed.** On `dev`, `DocumentList` reloads only when `refreshKey` changes, and that is bumped once at upload time (`onUploaded`), never when processing finishes. His fix polls every 3 s while any doc is `uploaded`/`processing`/`ocr_done`. That's correct. Minor: a document stuck in `processing` is polled forever, and `BatchUploadPanel` still runs its own 4 s poller. Both could share one source.
- **"Two flagged sections"** is ambiguous, so this is my reading. There were two status lists on the upload page ("Uploaded this session" in `BatchUploadPanel`, and `DocumentList`) that both showed `flagged`. He deleted the first and moved the delete button into the second. Separately there is `RiskFlagsPanel` (case-level `risk_flags` rows), which is a different thing that happens to share the word "flagged". He didn't address that naming collision. **Your call:** keep `RiskFlagsPanel` separate (my recommendation) and consider relabelling the *document* status (the review toast already says "flagged for correction").

## Item 10: similar search highlighting, and D5

- The highlighting bug is real. The old `HighlightedText` only matched the whole query as one contiguous string. This plausibly connects to the Marathi/Devanagari report of 2026-08-21 noted in `search_service.build_snippet`: when the Python `.find()` misses, the backend falls back to a word-overlap sentence, which the old frontend could never highlight. His tokenizer (`[\p{L}\p{M}\p{N}]+`, so combining marks are kept) fixes exactly that, **in exact mode, with no semantic search involved.** Caveats: it highlights every word of a multi-word query separately (including stopwords) even when the phrase is present, and it doesn't address NFC/NFD normalization mismatches.
- **Conflicts with D5: yes, the rest of it.** The Exact/Similar toggle, passing `mode` to the API, the `highlightFallback` violet branch and the changed search blurb all re-enable semantic search. He edited `DECISIONS.md` to mark D5 "Superseded by D8", added D8, and rewrote the Phase 4 row in `ROADMAP.md`. D8's justification ("the reviewer requested similar search") isn't recorded anywhere I can find. If that request was real, D5 should be superseded deliberately by you, not by this PR.

## Item 12: admin account creation (already exists)

- **Backend:** `POST /admin/reviewers` (`api/v1/admin.py`, `RoleRequirement(["Admin"])`) creates a user with the role **hard-coded to `Reviewer`**. There is also `GET /admin/users` and `POST /admin/assign-reviewer`. The admin itself is seeded from `ADMIN_EMAIL`/`ADMIN_PASSWORD` in `auth.py`.
- **Frontend:** `app/admin/users/page.tsx` → `UserManagementPage.tsx`, using `apiClient.admin.createReviewer`.
- **His `Frontend/src/lib/admin.ts` is a duplicate with zero importers** (dead code, contrary to D6). His notes acknowledge the feature already existed.
- If the real ask is an admin creating *other admins*, or other roles, that is new work. `RoleEnum` has both roles, but the endpoint pins `Reviewer`.
- Pre-existing, not his: the create-reviewer response echoes the plaintext password back.

## Buckets

### Already done in our work
- Item 3 (SSO buttons), item 12 (admin creation), and the fabricated HomePage stats (Phase 3). His diff re-does none of this except via no-ops.
- Not fully done by Phase 3: `LoginPage.tsx` still had "24k+ records / 99.9% uptime / SOC 2 ready". His change removes it, so that belongs in the next bucket.

### Useful and compatible, take as is
- `layout.tsx`, `AppNavigation.tsx`, `AuthContext.tsx` (placeholder email), `DashboardPage.tsx`
- `LoginPage.tsx`: rebrand plus removal of the fabricated stats and the "SOC 2 ready" claim
- `HomePage.tsx` (after a visual check)
- `CaseWorkspacePage.tsx` header fixes (`PV-2408` fallback, "Miami, FL", fake `SV-9912`), **except the search-description hunk**
- `DocumentList.tsx`, `BatchUploadPanel.tsx` (items 8 and 9)
- `ReviewPage.tsx` (item 11)
- `CaseCreationPage.tsx` and the frontend types in `client.ts`/`hooks.ts` (items 5 and 6, frontend half)
- `.env.example`: the old `$env:ADMIN_EMAIL="..."` lines were invalid dotenv, and a placeholder password replaces `admin123`
- `image_enhancement.py` / `pipeline_service.py`: error text added to the fallback log line

### Useful but needs changes
- Item 6 backend: `schemas/cases.py`, `api/v1/cases.py`, `test_case_create_schema.py`, plus the PDF rows. Decide the nullable-column question first.
- Item 7: `tasks/*`, `docker-compose.yml`, `backend/Dockerfile`, `.dockerignore`, `config.py`, `requirements.txt`, `documents.py`, `docs/SETUP.md`, the Celery section of `ARCHITECTURE.md`. Fixes: items 1–4 and 6–8 above.
- Item 10: `HighlightedText.tsx`. Keep only the term-splitting. Drop `highlightFallback`.
- `documents.py` enhanced-image error messages: reasonable, but they bundle into the item 7 file.
- **Report PDF export via authenticated stream** (`report_builder.py`, `report_builder_service.py`, `schemas/report_builder.py`, `ReportBuilderPage.tsx`, `client.ts`, `test_report_builder_service.py`). **Not on his checklist.** The motive is legitimate (a signed Storage token in the address bar/history). But it changes the export API from JSON to binary and deletes `ReportExportResponse`, with no recorded decision. Technically sound and tests pass. Take it only if you want it, as its own change.

### Conflicts with DECISIONS.md
- `docs/DECISIONS.md` (D5 "superseded", new D8, and a rewrite of the outstanding-verification wording that drops the "164 passing" record)
- `docs/ROADMAP.md` (Phase 4 row rewritten)
- `CaseSearchPanel.tsx` (Exact/Similar toggle, `mode` passed to the API, semantic explainer text)
- `HighlightedText.tsx`'s `highlightFallback` branch
- `CaseWorkspacePage.tsx` search description ("…find semantically related passages")

### Low quality or risky
- `Frontend/src/lib/admin.ts`: dead duplicate of an existing feature.
- `docs/SESSION_CHANGES.md` (152 lines, AI-written change log). Overstates: it says `test_document_tasks.py` covers "failure handling", but the file is one happy-path test. It shouldn't live in `docs/` next to DECISIONS/ROADMAP.
- `docs/ARCHITECTURE.md` reword: rewrites history ("Planned delta" → "Risk-flag extraction and review") beyond what the Celery section needs.
- One monolithic commit mixing unrelated changes, including an unrequested security change, so it can't be cherry-picked per item as is.

## Recommendation per item (waiting on your decision)

A single commit means `git cherry-pick` takes everything or nothing. To keep his authorship while taking a subset: `git cherry-pick -n 963e415`, drop or trim the files we don't want, then `git commit --author="Aditya2OO4 <…>"`. Anything I reimplement gets a `Co-authored-by:` trailer.

| # | Recommendation |
|---|---|
| 1 | **Cherry-pick** (as part of the one trimmed commit) |
| 2 | **Cherry-pick** `HomePage.tsx` + `LoginPage.tsx`, after you look at them in a browser |
| 3 | Nothing to take for the buttons. The `LoginPage.tsx` stats removal comes along with item 2. |
| 4 | **Cherry-pick.** Separately, I'd delete `FullCaseDashboard.tsx` and stop defaulting `risk`/`priority`/`confidence` (D6). |
| 5 | **Cherry-pick**, once you confirm "badge only" is what you meant |
| 6 | **Cherry-pick the frontend. Reimplement the backend** (nullable migration vs `""`, PDF rows) after you check the Supabase constraint. |
| 7 | **Cherry-pick, then fix on top** in follow-up commits (lazy import, `/process` guard, drop result backend, retry-safety, add tests, write D9). First confirm you want Redis and a worker to operate. |
| 8 | **Cherry-pick** |
| 9 | **Cherry-pick** the list fix, and decide the "flagged" naming question |
| 10 | **Cherry-pick, then trim** to the term-splitting only, and reject the semantic parts. Or you formally supersede D5, which I'd advise against without a recorded reviewer request. |
| 11 | **Cherry-pick** |
| 12 | **Drop** (no cherry-pick, delete `lib/admin.ts`). New work only if you want admin-creates-admin. |
| — | PDF export hardening: separate decision, own change, **cherry-pick later if approved** |
| — | `SESSION_CHANGES.md`, D8, the ROADMAP/ARCHITECTURE rewrites: **don't take** |
