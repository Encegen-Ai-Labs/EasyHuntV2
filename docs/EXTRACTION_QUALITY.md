# Extraction quality: evaluation set, consistency, grounding, lawyer corrections

**Status:** plan only, awaiting approval. Nothing in this document has been implemented, and no code was changed to write it.
**Date:** 2026-10-07
**Planned against:** `origin/dev` (`2a95a91`, contains PR #26) plus branch `pr27-intern-merge` (`95154d4`), which is not merged yet. I read that branch's diff only and did not edit it.
**Note:** the local `dev` ref is stale (`fc6d7f5`). Use `origin/dev` as the base.

## 0. What I found in the code

Everything below was read from the code. Nothing was run, because I had no `.env`, no Supabase access and no sample documents.

### Extraction calls today

| Call | File | Used by |
|---|---|---|
| Page transcription (plain text) | `page_extraction_service.extract_page_text` | `document_router` for VLM pages |
| Page transcription **and** fields in one call (text, then `===FIELDS===`, then JSON) | `page_extraction_service.extract_page_text_and_fields` | single-page documents only |
| Fields from merged transcription | `llm_extractor.extract_structured_fields_from_text` | multi-page documents, and single pages that stayed on OCR |
| Whole-document image extraction | `llm_extractor.extract_from_image_path` and `extract_from_supabase_url` | **nothing in production.** Only `backend/test_extraction.py` calls it. |

On the consistency question:
- **Temperature:** `temperature=0.0` is already set on all four calls. It is not the fix.
- **Structured output:** not used. No `response_mime_type`, no `response_schema`, no `seed`. The prompts ask for "raw JSON, no backticks" and the code strips fences and calls `json.loads`. A malformed response becomes a failed document ("Model returned invalid JSON").
- **Prompt version:** none. Prompts are inline strings, so there is no way to tell which prompt produced a stored extraction.
- **Model:** the literal `"gemini-3.5-flash-lite"` is repeated 17 times across four service files (`llm_extractor`, `page_extraction_service`, `pipeline_service`, `report_draft_service`). If Google moves what that name points to, behaviour changes silently and nothing records it.
- **Dedup:** `execute_analysis_pipeline` returns `already_processed` only when an `extractions` row exists for the same `document_id`. Uploading the same file again creates a new `document_id`, so the model is called again. This is why the same file gives different results.
- **Two stages compound the variance:**
  - Stage 1 is the VLM transcription. It is free text with the whole page as output, so it has the most room to vary.
  - Stage 2 extracts fields from that transcription. Any wording difference in stage 1 reaches the fields.
  - The router, the enhancement and Tesseract are deterministic for identical input. I expect the variance to come from the Gemini calls, but I have not measured it. §2.3 measures it and shows which stage it comes from.

### How raw and validated output are stored

- **`raw_json_output` and `validated_json_output`** are the same Python object at insert time (`pipeline_service.py:357-358`). So there is no "model's original" kept separately from anything the system later adjusts.
- **`validation.py`** computes `low_confidence_fields` but the pipeline never stores it. `needs_human_review` is always `True`, so every document is already reviewed. The new value from grounding (§3) is **which fields** the lawyer should look at first, not whether to review.
- **The router discards Tesseract text for VLM pages.** `_analyze_page` runs Tesseract on every page before routing and then drops the result when the page goes to the VLM. That text is a free, independent second reading, which is the most useful input for §3.

### Lawyer corrections today

You said ReviewPage edits don't persist. I could not reproduce that from the code. The path exists end to end:
1. `ReviewPage.handleSaveFieldEdits` sends a `PATCH /review/documents/{id}`.
2. `ReviewService.submit_document_review` writes `validated_json_output`, `human_correction` and `review_notes` onto the `extractions` row.
3. The query is invalidated, so the page refetches.

The code does show two weaknesses regardless:
1. **Overwrite, no history.** `human_correction` is set to the same full dict as `validated_json_output`. It is not a diff, so there is no record of what changed. A second save overwrites the first. There is no record of who changed which field, why, or under which model and prompt.
2. **Page-text edits destroy the original.** They overwrite `document_pages.original_text` / `english_text`. Only the merged `extractions.raw_ocr_text` keeps the original text.

Two things could still make saves fail live. I cannot check either without Supabase:
1. **Missing column.** Migration `0004` records that `review_notes` was missing from the live table and made every save return a 500 (PGRST204). It confirms `validated_json_output`, `reviewed_by`, `reviewed_at` and `status` exist. It does not mention `human_correction`. If that column is missing, every save fails the same way.
2. **A save that looks fine but doesn't stick.** A failed PATCH shows an error toast (the client returns `{success: false}` and `ReviewPage` toasts it), so a missing column would not be silent. If you saw "saved, then reverted with no error", the cause is elsewhere and I'd need to see it happen.

**Question for you:** what exactly did you see: an error toast, or a save that appeared to work and then reverted? Phase 5 includes an idempotent migration that adds any missing columns, so it is safe either way.

### Effect of the pr27 branch

On the two extractor files, the branch only adds `"rate_limited": is_rate_limit_error(e)` to failure results, plus the `rate_limit` import. It also touches `pipeline_service.py` (9 lines), `document_dispatch.py` and the Celery tasks (new), `config.py` and `search_service.py`. My plan interacts with it in three ways:
- **Failures are never cached.** A `rate_limited` failure must not be stored as a result.
- **Celery changes the pipeline's call path.** The Celery task must go through the same cache and the same DB-free core function (§1.5).
- **Merge conflicts.** Phases 1, 3 and 4 edit `llm_extractor.py`, `page_extraction_service.py` and `pipeline_service.py`. They start only after the branch is merged, as you asked.

---

## 1. Evaluation set

### 1.1 Layout

The corpus holds client legal documents, so it must not be committed. The repo already untracks raw client sources (`6651e45`, `3ff6193`). Real data goes in a gitignored folder. Only the code and one synthetic example case are committed.

```
backend/eval/                         committed
  README.md
  expected.schema.json                JSON Schema for expected.json
  run.py                              the scoring script (§1.4)
  variance.py                         the variance test (§2.3)
  scorers.py                          per-field comparison rules
  example_synthetic/                  fake data, shows the format
    source.png
    expected.json
    meta.json

eval_data/                            GITIGNORED, or EVAL_DATA_DIR=<anywhere outside the repo>
  cases/
    0001_sale_deed_printed_mr/
      source.pdf                      the original upload, byte for byte
      expected.json                   the correct answers
      meta.json                       type, split, language, handwriting, notes
      transcript.txt                  OPTIONAL: the correct full text
    0002_mutation_handwritten_hi/
      ...
```

- **One folder per document, ID prefix numeric.** Names are stable because results key on the folder name.
- **`source.*` is never modified.** The script also stores its SHA-256, so a duplicate of the same file under two IDs is detected.
- **`transcript.txt` is optional.** When present, the script also scores stage 2 alone, with the correct text as input. That separates "the transcription was wrong" from "the field extraction was wrong". If you only have corrected fields, skip it.

### 1.2 `meta.json`

```json
{
  "id": "0001_sale_deed_printed_mr",
  "document_type": "sale_deed",
  "split": "holdout",
  "language": "mr",
  "handwriting": "none",
  "pages": 4,
  "notes": "Registered sale deed, typed Marathi, stamp on page 1"
}
```

- **`split`** is `"example"` or `"holdout"`. See §1.6.
- **`handwriting`** is `"none" | "partial" | "full"`. It drives the breakdown that matters most for §3.

### 1.3 `expected.json` (the format to approve before you fill it in)

Key names are **identical to the extraction output** (`owner_name`, `transaction_date`, ...). A corrected `validated_json_output` from the database can therefore be dropped in with only `full_text` and the `*_confidence` keys removed. A small `import_extraction.py` helper will do that conversion.

```json
{
  "schema_version": 1,
  "labelled_by": "Adv. <initials>",
  "labelled_on": "2026-10-12",
  "fields": {
    "document_type": "sale_deed",
    "owner_name": "Ramesh Kumar Patil",
    "previous_owner_name": "Sunil Dattatray Patil",
    "survey_number": "45/2B",
    "transaction_date": "1998-03-12",
    "transaction_type": "sale",
    "property_location": "Village Wagholi, Tal. Haveli, Dist. Pune",
    "property_boundaries": null,
    "area": "2 Acre 10 Gunthas",
    "registration_number": "1234/1998",
    "language_detected": "Marathi"
  },
  "alternates": {
    "owner_name": ["रमेश कुमार पाटील", "Ramesh K. Patil"]
  },
  "chain": [
    { "order": 1, "owner": "Sunil Dattatray Patil", "date": "1975-06-01", "type": "Inheritance", "survey": "45/2B" },
    { "order": 2, "owner": "Ramesh Kumar Patil",    "date": "1998-03-12", "type": "Sale Deed",   "survey": "45/2B" }
  ],
  "red_flags": [
    { "type": "encumbrance", "source_text": "mortgaged to ... Co-op Bank" }
  ],
  "unlabelled": ["property_boundaries", "red_flags"]
}
```

Rules:
- **`null` is an answer.** `"previous_owner_name": null` means "the correct extraction is null". A model that returns a name there is **spurious**, which is worse than a miss.
- **`unlabelled`** lists fields you did not verify. They are skipped, not counted as wrong. This lets you add partially checked documents without poisoning the score.
- **`alternates`** lists acceptable variants of the same value (a different script, an abbreviation). `value` is the canonical one. Alternates only widen what counts as a match. They never change the canonical answer.
- **Dates** are `YYYY-MM-DD`, with `YYYY-01-01` for year-only, matching the prompt's existing rule.
- **`chain`** is optional. Omit it or list it under `unlabelled` and it is skipped.

### 1.4 What the script reports

```
python -m eval.run --split holdout --runs 1 --no-cache [--stage end-to-end|fields-only] [--compare baseline.json]
```

Per field, each document gets one outcome:

| Outcome | Meaning |
|---|---|
| `correct` | exact match after normalisation, or an `alternates` match |
| `close` | names/free text only: similar enough (below) but not identical |
| `wrong` | a value was returned and it is not the right one |
| `missing` | expected a value, got `null` |
| `spurious` | expected `null`, got a value |

The script prints separate **strict** (correct only) and **lenient** (correct + close) scores. Wrong and spurious are reported apart from missing, because for title verification a confidently wrong answer is worse than an empty one.

**Comparison rules per field type:**

| Field type | Fields | Exact rule | Close rule |
|---|---|---|---|
| Enum | `document_type`, `transaction_type` | string equality | none |
| Name | `owner_name`, `previous_owner_name`, chain `owner` | NFC, casefold, strip honorifics (Shri/Smt/Mr/श्री/श्रीमती...), collapse spaces and punctuation | token-set similarity at or above 0.85 (rapidfuzz), or initials expanding to the full name |
| Identifier | `survey_number`, `registration_number` | digits normalised to ASCII (Devanagari/Tamil/Telugu/Kannada digits), spaces and case removed, `/` and `-` kept | same identifier token after dropping prefix words ("Gat No.", "S.No.") |
| Date | `transaction_date`, chain `date` | ISO equality | none. A day/month swap is reported as its own error class so you can see how often it happens |
| Area | `area` | number and unit equal after unit synonyms | numeric within 0.5% and same unit |
| Free text | `property_location`, `property_boundaries` | none | token F1 at or above 0.8 |
| Language | `language_detected` | normalised equality | none |
| Chain | `chain` | owner sequence equal | per-link owner (close), date (exact), type (exact), plus link-count match |
| Red flags | `red_flags` | precision and recall by `type` | `source_text` overlap above 0.6 counts as the same flag |

**Breakdowns** (each cell shows `n`, because with ~10 documents a percentage without `n` misleads):
1. **Type x field matrix**, by the document's `document_type`.
2. **Critical fields**, reported on their own: `owner_name`, `previous_owner_name`, `survey_number`, `transaction_date`, `registration_number`, `area`.
3. **By handwriting** (`none` / `partial` / `full`) and by routed source (`ocr` / `vlm`).
4. **By language.**

**Outputs:** console table, `eval_runs/<timestamp>/results.json`, `report.md` with a per-document diff of expected vs got, and a `baseline.json` that `--compare` reads.

**Stop rule, mechanical:** `--compare baseline.json` exits non-zero and prints the field(s) if any `(document_type, field)` mean score is lower than the baseline's. That is the "a change lowers any field's score" stop condition, so it is checked by the script and not by my judgement.

**Caveat:** with ~7 scoring documents, one document moves a field by about 14 points, and some type x field cells have `n` of 1 or 2. Run-to-run noise could trigger the stop rule on its own. So baselines and comparisons are means over the same number of runs (§2.3), and every report states which differences are within the baseline's own run-to-run spread. The corrections pipeline (§4) is the long-term fix: it grows the set from real reviews.

### 1.5 A DB-free core function

The script can't use `execute_analysis_pipeline`, which needs Supabase (it uploads enhanced images, writes rows). Phase 1 extracts the pure part into `extract_document_bytes(file_bytes, mime_type) -> dict`: rasterize, enhance, route, merge, field extraction, validation, with no I/O. `execute_analysis_pipeline`, the Celery task and the eval/variance scripts all call it, so they cannot diverge. This touches `pipeline_service.py`, so it waits for the pr27 merge.

### 1.6 Train/example vs holdout split (~10 documents)

- **3 worked examples, 7 holdout.** Ten is tight. Four examples would leave six scoring documents, with several types at `n=1`.
- **Choose examples for coverage.** Pick the 3 so they cover different document types and at least one handwritten page. A type with only one document stays holdout-only: a type with no scoring document can't be evaluated at all.
- **Examples go in the prompt as text, not images**, to keep tokens down: transcription in, expected JSON out. For the single-page VLM path the model sees an image, so the examples teach the output conventions (null handling, year-only dates) and not reading.
- **The script enforces the split:**
  - `--split holdout` is the default and the headline number.
  - Example documents can be run with `--split example`, but they are labelled "contaminated, not comparable" and excluded from every headline figure.
  - The script refuses to start if the prompt builder's example IDs and the holdout set overlap, by folder ID or by source SHA-256.
- **Do not tune on the holdout set repeatedly.** Each prompt tweak made after looking at holdout failures leaks them into the prompt. Add new documents instead (§4.4).
- **Example values can leak into outputs.** A model may copy an example's names into an unrelated document. The grounding check (§3) catches this, because those names won't be in the page, and has an explicit blocklist of example values.
- **Whether examples help at all is measured, not assumed.** They are Phase 6 and kept only if the holdout score does not drop and the critical fields improve.

---

## 2. Consistency

### 2.1 Cache by content

**Goal:** the same file returns the same stored result, with no second model call.

**Key:** `sha256(file bytes)` + `model` + `pipeline_version`.

`pipeline_version` is **computed**, not hand-bumped: a short hash over the prompt texts, the response schema, the model name, the generation config (temperature, seed), and the pipeline parameters that change the output (`RASTER_DPI`, `MAX_IMAGE_DIMENSION_PX`, `ROUTER_HANDWRITING_THRESHOLD`, `OCR_FALLBACK_CONFIDENCE`). Editing any prompt invalidates the cache automatically, because a forgotten manual bump is the usual way a cache hides a regression.

**Two layers:**

| Layer | Key | Stores | Why |
|---|---|---|---|
| Document (the one you asked for) | file SHA-256 + model + `pipeline_version` | final extraction dict | same file, same answer |
| Page transcription (recommended) | SHA-256 of the *enhanced* page PNG + model + transcription-prompt version | page text | lets the eval hold stage 1 fixed while stage-2 prompts change, so a field-prompt change is measured on its own |

**Storage:** new table `extraction_cache(key text primary key, layer text, model text, pipeline_version text, content_sha256 text, result jsonb, created_at timestamptz)` (migration `0007`, run manually like `0001`-`0006`). Code sits behind a small interface with two implementations:
1. **Supabase**, for the app.
2. **Local file store**, for the eval and variance scripts, which have no Supabase.

A cache read or write error is treated as a miss and logged, never as a failed document.

**Never cached:**
- **Failures,** including the pr27 `rate_limited` results.
- **Results that fail schema validation.**

**Bypass:**
- `--no-cache` on the scripts.
- A "re-extract" flag on the process endpoint for admins.

**Limits:**
- **Exact bytes only.** The same document re-scanned, re-saved as a PDF or photographed again is a different file and misses. The page-level layer catches identical rendered pages inside a re-saved PDF, but not a different scan.
- **A cached wrong answer stays wrong,** until the prompt changes or someone bypasses the cache.
- **Corrections and the cache:** if the same file was reviewed before, show the earlier lawyer-corrected values in the review screen as a suggestion. Do not apply them silently. This is a decision for you (open questions).

The hash is computed once at upload and stored on `documents` as `content_sha256` (same migration).

### 2.2 Make the output deterministic where we can

1. **Structured JSON output with a schema** for the text-mode field call: `response_mime_type="application/json"` plus `response_schema` generated from one pydantic model that also validates the result. Enums (`document_type`, confidences, red-flag types) become real enums, nullable fields are explicit, and the fence-stripping `_clean_json_response` stops being load-bearing. Property order puts evidence before value (§3.2) because generation order affects faithfulness.
2. **`seed`** added to every `GenerateContentConfig`, alongside `temperature=0.0` (already there).
3. **One model constant,** and record the exact model version the API reports for each call (if the SDK exposes it on the response; I have not verified this) on the extraction row.
4. **The combined single-page call is the exception.** It uses a `===FIELDS===` delimiter because the transcription is long, free text, and the existing comment explains why it avoids JSON for that. A schema would force the entire response to be JSON, which could remove the delimiter format or put the transcription inside a JSON string. I will not assume which is better. Phase 3 scores three variants on the eval set (delimiter as now; a `{transcription, fields}` schema; two separate calls) and keeps the one with the best holdout score.

**I have not checked** how `gemini-3.5-flash-lite` treats `seed`, thinking settings or schema constraints. The first call in Phase 3 verifies that it accepts the config. Gemini does not promise bit-identical output at temperature 0, which is why the variance test below exists and why the cache is still needed after this.

### 2.3 Variance test

```
python -m eval.variance <path-to-document> --n 10 --no-cache
```

Runs the whole pipeline N times on one document, with cache off, and reports:
- **Per field:** number of distinct values, the most common value and its share, and for names the minimum pairwise similarity.
- **Per stage:** whether the *transcription* changed between runs (character-level similarity min/mean), or only the extracted fields did. This says whether to spend effort on stage 1 or stage 2.
- **Routing:** whether the OCR/VLM route changed between runs for any page. I expect this to be stable, but it is cheap to confirm.
- **A verdict line per field:** `stable` / `unstable`, plus a total Gemini call count so the cost is visible.

It also runs over the whole holdout set (`--n 5`) to produce the **baseline** in §5: the mean per `(document_type, field)` over 5 runs, with its spread. Every later comparison uses the same N.

---

## 3. Grounding check (hallucination)

### 3.1 The rule

For each extracted **name, date and number**, the checker looks for evidence in the document and sets a status. It is a deterministic Python module, with no extra model call.

| Status | Meaning | Effect on confidence |
|---|---|---|
| `corroborated` | found in the transcription **and** in the independent Tesseract text | keep the model's confidence |
| `grounded` | found in the transcription only | keep, but cap at `medium` on handwritten/VLM pages |
| `weak` | partial or fuzzy match only | cap at `medium` |
| `ungrounded` | not traceable anywhere | force `low` |
| `derived` | a date or number legitimately computed, not copied (an era conversion, year-only) | cap at `medium`, annotated |

"Goes to lawyer review" is already true of every document. What changes is **per field**: ungrounded and single-source fields get a visible badge, and the existing per-field confidence badge in `ReviewPage` already renders `<field>_confidence`. So lowering that value surfaces it with no frontend change. A one-line entry also goes into `validation_errors`, e.g. `owner_name not found in document text`.

### 3.2 Where the evidence comes from

1. **Source quotes from the model.** The schema asks for `evidence: { <field>: { quote, page } }` next to the flat fields. Existing consumers (`chain_service`, `validation.py`, `ReviewPage`) keep reading the flat keys unchanged. The checker verifies the quote exists in the transcription (fuzzy, at or above 0.9) and that the value appears inside the quote.
2. **The transcription itself,** after stripping the bracket annotation tags, as `pipeline_service` already does for field extraction.
3. **Tesseract text, kept instead of discarded.** The router already computes it for every page, including pages sent to the VLM. Keeping it gives an independent reading.

### 3.3 Per-field matching

- **Names:** normalise as in §1.4, then require each token of the name to appear with token similarity at or above 0.85. Honorifics are ignored. **Script matters:** if the document is in Devanagari and the model returns the name in Latin letters, plain string matching fails every time. The checker needs a transliteration step (to a common scheme) before comparing, and the prompt should say which script names are returned in. I do not know which your lawyers use, so this is an open question.
- **Dates:** parse the ISO value, generate the renderings it could have in the text (`12/03/1998`, `12-3-98`, `12th March 1998`, Hindi/Marathi month names, Devanagari digits), and look for any. Year-only (`YYYY-01-01`) matches on the year alone and is marked `derived`. Vikram/Shaka Samvat dates converted to the Gregorian calendar can't be found verbatim, so they are marked `derived`, not `ungrounded`.
- **Numbers (survey, registration, area):** digits normalised across scripts, then the digit sequence including its `/` and `-` separators must appear as a token. For area, the number must appear and the unit must be a known synonym. Known OCR confusions (0/O, 1/l, 5/S, 8/B) are allowed and downgrade the status to `weak`.
- **Red flags and chain:** each `red_flag.source_text` must appear in the text. A flag whose quote cannot be found is **kept and marked "unverified quote"**, never dropped. This follows the codebase's existing stance (`_iter_valid_red_flags` fails toward more scrutiny): a missed dispute costs far more than one extra flag a lawyer dismisses.
- **Example-value blocklist:** any extracted value identical to a value inside the prompt's worked examples, but absent from the page, is `ungrounded` with reason `copied_from_example`.

Results are stored per field in a new `extractions.grounding_json` column (migration `0008`). `raw_json_output` is no longer the same object as `validated_json_output`: raw stays as the model returned it, validated carries the adjusted confidences.

### 3.4 What this can and cannot catch on handwritten pages

Tesseract on handwritten Devanagari, Tamil, Telugu or Kannada is close to unreadable, which is why the router sends those pages to the VLM. So on exactly those pages the independent reading is weakest.

**It can catch:**
- **Stage-2 invention.** The field extractor returns a name, date or number that is not in the transcription it was given. This is the most common hallucination and the checker finds it without needing Tesseract.
- **Fabricated or altered quotes** in `evidence` and `source_text`.
- **Copying from the prompt's examples.**
- **Values next to `[illegible]`.** A value located within a few tokens of an `[illegible]` marker is flagged `weak`.
- **Inconsistent spelling** of the same party across pages or within the transcription.
- **Impossible values:** malformed or implausible dates, impossible digit patterns.
- **Printed numerals on mixed pages.** Tesseract is usually good with digits and stamps even where the surrounding text is handwritten, so a survey or registration number it agrees with becomes `corroborated`.

**It cannot catch:**
- **A VLM misreading that is then used consistently.** If the VLM reads "1964" as "1984" or one name for another, the transcription contains the error and stage 2 faithfully extracts it. The quote is "found" in the text, so the check passes. The VLM transcript is the only source on those pages, so a wrong-but-plausible reading is invisible to this check. Nothing short of a second independent read can find it.
- **A wrong name that happens to be a real name elsewhere on the page.**
- **Tesseract disagreement on handwriting means nothing.** Garbage OCR on a handwritten page is not evidence against the VLM. The checker therefore gives Tesseract no weight on pages the router classed as handwriting, apart from the digit case above.

**Policy for handwritten pages:** a field supported by the VLM transcript only is a distinct state, `single_source`, not "grounded" and not "ungrounded". Its confidence is capped at `medium` and the review screen can show a "VLM only" tag. This matches the pipeline's existing "handwritten means flag regardless" rule in `validation.py`, applied per field.

**Optional later step, decided after the numbers (not planned yet):** a second independent read, such as a second VLM pass with a different prompt, with field-level agreement as a signal. It would catch non-systematic misreads and would roughly double the cost on handwritten pages. It would not catch a misreading both passes make.

### 3.5 Measuring the check itself

The eval script adds a `--grounding` report using the labelled holdout documents. Per field, it gives:
- **Catch rate:** of the extracted values that are *wrong*, how many were flagged `ungrounded`, `weak` or `single_source`.
- **False-alarm rate:** of the *correct* values, how many were flagged.

Both are split by handwriting level. That is the evidence for the "can and cannot catch" claims above, on your documents. The thresholds (0.85, 0.9) are starting values and get tuned on this report, not guessed.

---

## 4. Lawyer corrections as a dataset

### 4.1 Principles

1. **Never overwrite the model's output.** `raw_json_output` is written once, at extraction, and not touched again.
2. **Keep `validated_json_output` as "current best answer".** All existing readers keep working.
3. **Record every change as an append-only row** with enough context to be useful later.

### 4.2 Table `extraction_corrections` (migration `0009`, run manually)

One row per field change per save.

| Column | Meaning |
|---|---|
| `id`, `created_at` | |
| `extraction_id`, `document_id`, `case_id` | where it happened |
| `content_sha256` | joins back to the exact source file, and to the cache |
| `field_path` | `owner_name`, `chain[1].date`, `red_flags[0]`, `page[3].original_text` |
| `change_type` | `edit` / `clear` / `add` / `remove` / `confirm` |
| `original_value` | what the model produced (from `raw_json_output`) |
| `previous_value` | what was there just before this save (for repeated edits) |
| `corrected_value` | what the lawyer saved |
| `reason` | short enum (`misread`, `wrong_field`, `hallucinated`, `format`, `other`) plus optional free text. Optional in the UI. |
| `corrected_by`, `revision` | reviewer id; counter per extraction |
| `model_used`, `pipeline_version`, `source` (`ocr`/`vlm`), `handwriting`, `model_confidence`, `grounding_status` | the context at the time, so errors can later be grouped by cause |

`confirm` rows are written when a document is approved: one per key field the lawyer left unchanged. Confirmed-correct values are as useful to the dataset as the corrections, since they are the true negatives.

A unique index on `(extraction_id, revision, field_path)` makes a retried save idempotent. `supabase-py` has no multi-statement transaction, so the service inserts the correction rows first and updates the `extractions` row second. If the second step fails, a retry reuses the same `revision` and the unique index prevents duplicates. A Postgres function (`apply_review`) would make it truly atomic, at the cost of more SQL to maintain. Recommendation: start with the ordered approach.

### 4.3 Code changes

- **Backend:** `ReviewService.submit_document_review` computes the diff server-side. The API stays backward compatible: the PATCH body is still `validated_output` + `review_notes` + `decision`, plus an optional per-field `reasons` map. `human_correction` becomes the **diff only**, which is what its schema description already says. Page-text edits in `documents.py::update_document_page` write correction rows too, with the old text kept, instead of just overwriting.
- **Backfill:** a script diffs existing rows' `human_correction` against `raw_json_output` to seed the table from reviews already done. Because `raw_json_output` and `validated_json_output` were identical objects at insert, this is accurate.
- **Frontend:** `ReviewPage` gains an optional "reason" select per edited field. Two gaps are fixed in passing:
  - `handleFieldChange` stores everything as strings, which would turn a boolean field into `"true"`. The diff compares like with like, and an emptied input becomes `null`.
  - The ownership chain and red flags are display-only today, so a wrong chain link can't be corrected. They become editable in a later sub-step. Until then they are not in the dataset.

### 4.4 From corrections to the evaluation set

`python -m eval.export_corrections` writes approved documents into the §1 folder format: `source.*` from storage, `expected.json` from the final reviewed values, and `unlabelled` listing any field no human touched or confirmed. A document enters the eval set only after:
1. **A lawyer approved it,** and
2. **You assign its split.** New documents default to `holdout`, never `example`.

Export is local, to the gitignored folder. The corrections table has the same access rules as `extractions`; `corrected_by` stores a user id, not a name.

**What the dataset is used for, with no training:**
1. It grows the evaluation set.
2. Counting corrections by `field_path`, `reason`, `source` and `handwriting` shows the most common error patterns, which guides prompt and grounding changes.
3. It supplies candidate worked examples.
4. It measures the grounding check's catch rate on real mistakes.

---

## 5. Phases and gates

You asked for phases to run without stopping for approval. Stops happen only if a change lowers any field's score on the evaluation set, or if I need your real `.env` or Supabase access. All phases wait until `pr27-intern-merge` is merged into `dev` and you tell me.

| # | Phase | Behaviour change? | Files | Needs from you |
|---|---|---|---|---|
| 1 | Evaluation harness: DB-free `extract_document_bytes`, `eval/` package, scorers, importer | No | `pipeline_service.py`, new `eval/` | none to build; unit tests use recorded outputs |
| 2 | Variance test and **baseline** | No | new `eval/variance.py` | **`GEMINI_API_KEY`**, your filled `eval_data/` |
| 3 | Determinism: model constant, `seed`, structured output + schema (variants scored), content-hash cache | Yes | `llm_extractor.py`, `page_extraction_service.py`, migration `0007` | **Supabase** to apply `0007`; stop rule applies |
| 4 | Grounding: keep Tesseract text, evidence in schema, checker, `grounding_json` | Yes | `document_router.py`, `pipeline_service.py`, new `grounding.py`, migration `0008` | **Supabase** for `0008`; stop rule applies |
| 5 | Corrections: table, diff, backfill, ReviewPage reasons, export script | No (to extraction output) | `review_service.py`, `documents.py`, `ReviewPage.tsx`, migration `0009` | **Supabase** for `0009` |
| 6 | Worked examples in the prompt (optional) | Yes | prompt text | stop rule applies |

**How the stop rule is applied:** after each behaviour-changing phase I run `python -m eval.run --compare baseline.json`. If it exits non-zero I stop and show you the fields, the documents and the before/after values. I do not retune and retry on my own.

**What I cannot do without you:**
- **Live runs** (Phase 2 onward) need `GEMINI_API_KEY`, and the filled `eval_data/`. I will not read your `.env`. Either you run the commands (`! python -m eval.run ...` in this session) or you give me the key.
- **Applying migrations** needs Supabase. The `.sql` files will be written like `0001`-`0006` for you to run.
- **Behaviour changes without a baseline.** If the eval set is not filled in by the time Phase 3 starts, I will build Phases 1, 2 and 5 and hold Phases 3, 4 and 6, because a change that cannot be scored cannot be checked against your stop rule. Tell me if you want something different.

Tests: the backend suite is already 166 tests on the pr27 branch (per `docs/PR.md`). Each phase adds unit tests that mock Gemini the way the existing tests do (`monkeypatch` on `generate_content`), so CI does not need the key.

## 6. Questions for you

1. **Corrected extractions:** what format are they in: JSON exports of `validated_json_output`, the finished `.docx` reports, or something else? This decides whether the importer reads JSON or I write a different conversion.
2. **Names script:** are the correct names in your corrected set in English letters, in the document's script (e.g. Devanagari), or both? This decides the transliteration step in the scorer and in the grounding check.
3. **The "edits don't persist" report:** an error toast, or a save that looked fine and then reverted? (§0)
4. **Re-uploaded files that were reviewed before:** show the earlier corrected values as a suggestion in the review screen (my recommendation), apply them automatically, or ignore?
5. **3 examples and 7 holdout** acceptable? And can the 3 examples be chosen from your 10 once you label them?
6. **Behaviour phases without a baseline:** hold them, as proposed above, or proceed?

## 7. Out of scope

- Training or fine-tuning any model, as you asked.
- Changing the OCR engine (D1 stands).
- The unused whole-document path (`extract_from_image_path` / `extract_from_supabase_url`). It is not called in production. I would remove it in a separate cleanup and not extend it. Say so if you want that included.

---

## 8. Revisions after review (2026-10-09)

Supersedes §5 and §6 where they differ. Still **not started**: implementation begins only when the user says `pr27-intern-merge` is merged into `dev`.

### 8.1 Decisions

- **Hold every behaviour change** until the evaluation set is filled in and a baseline exists. That includes structured JSON output with a schema and `seed` (they change extraction behaviour, so they are gated like any prompt change), grounding confidence overrides, and worked examples.
- **Safe phases, in this order**, autonomous, tests passing at each commit, short report after each:
  1. **a.** Evaluation harness and scorer (`eval_data/` gitignored, `expected.json` as in §1.3, `--compare baseline.json` exits non-zero on any field drop).
  2. **b.** Content-hash cache keyed on hash + model + prompt version.
  3. **c.** Variance test.
  4. **d.** Corrections table (append-only) plus export into the evaluation-set format.
- **Safe means extraction output does not change.** `has_handwritten_content` missing stays `True` (the `validation.py` default).
- **Names:** if the corrected set has both document-script and transliterated forms, the scorer reports the document-script score and the transliteration score separately. A transliteration mismatch is not an extraction error. (Which case applies is still unanswered.)
- **Hard stops:** do not read `.env`; do not connect to Supabase or run migrations (write `.sql` files and list the apply order); do not push or merge; stop and ask if `GEMINI_API_KEY` is needed.
- **Intern confirmed** `human_correction` (jsonb) and `review_notes` (text) exist in the live `extractions` table, so the missing-column theory in §0 is dropped.

### 8.2 Cache: force refresh

A lawyer who re-uploads because the first read looked wrong must be able to get a fresh extraction.
- **Upload path:** a `force_refresh` option on upload and on `POST /documents/{id}/process`. It skips the cache read and, on success, overwrites the cache entry. Failures are still never cached, including pr27's `rate_limited` results.
- **UI:** a "Re-extract (ignore saved result)" control in the upload panel and on the review screen.
- **Visibility:** every extraction records `served_from_cache`, the cache entry's `created_at` and its `pipeline_version`. The review screen shows a "Saved result from <date>" badge when a cached result was served, so it is never mistaken for a fresh read.
- `execute_analysis_pipeline` returns `already_processed` for any document id that already has an `extractions` row. So force refresh on an existing document must replace that row deliberately, and first copies the old row's `raw_json_output` and any lawyer edits into the corrections history (phase d). Edits are not lost silently.

### 8.3 "Edits don't persist": second trace

With the missing-column theory removed, I traced payload shape, status codes, refetch, RLS and the overwrite. I could not reproduce a failure from the code alone. Candidates, most likely first:

1. **Duplicate `extractions` rows for one document (one SQL query confirms it).** `execute_analysis_pipeline` does check-then-insert (`select` at line 192, `insert` at line 376) with no lock. `POST /documents/{id}/process` can run while the batch or Celery path is processing the same document, and nothing in the repo records a unique constraint on `extractions.document_id`. The live schema isn't in version control. The `GET` that feeds ReviewPage and the `PATCH` both use `select_one`, which takes the first row with **no `ORDER BY`**. An `UPDATE` writes a new row version, which can change which duplicate comes back first. The next fetch can then return the *other* row, so the edit looks reverted while the saved row is intact. To check, run in the Supabase SQL editor:
   ```sql
   select document_id, count(*), array_agg(id order by created_at)
   from extractions group by document_id having count(*) > 1;
   ```
   If it returns rows, that is the cause or a contributor. Fix: a unique constraint on `document_id` (after de-duplicating) and an explicit `ORDER BY` in the review lookup.
2. **A zero-row update looks like success.** `BaseRepository.update` returns `response.data`. PostgREST answers 200 with an empty list when no row matched or RLS hid the row. `submit_document_review` then returns `"extraction": None` with status 200, and the frontend treats any 200 as success. `review.py` uses `get_supabase_client()` (`SUPABASE_KEY`), while `flags.py` and `reports.py` use the service-role client for the same `ReviewService`. If `SUPABASE_KEY` is not the service-role key and RLS is on for `extractions`, reads could work while updates match nothing. The pipeline's inserts go through the same client and evidently work, so I think this is less likely, but I can't see the key or the policies. Fix regardless: return an error when the update changes no row.
3. **A flash of old values after Save.** `handleSaveFieldEdits` clears `editedFields` as soon as the PATCH succeeds. The page then shows the cached query data, which still holds the pre-edit values until `invalidateQueries` finishes refetching. That refetch creates a signed URL for every document in the case, so it is not instant. During that window it looks like a silent revert, and if the refetch fails the stale data stays. Fix: write the PATCH result into the query cache with `setQueryData` on success, then invalidate.
4. **Not the cause:** no other code writes `validated_json_output` after insert (only `review_service.py` and `pipeline_service.py` touch it), and `process` on an already-extracted document returns early without overwriting. Page-text edits use `document_pages`, a different table.

Payload shape and status codes check out: `ReviewSubmission` takes `validated_output`, `review_notes` and an optional `decision`; `PropertySystemException` becomes JSON with the right status; the client shows `detail` in a toast.

Fixes 2 and 3 and the lookup ordering do not change extraction output, so they fit in phase d. The unique constraint waits for your SQL result. **Please test on a real document and, if you can, run the duplicate-rows query**, so I fix the cause that actually exists.

### 8.4 Migrations (files only, none applied)

Apply order when the time comes:
1. `0007_extraction_cache.sql`: cache table, `documents.content_sha256`.
2. `0008_extraction_corrections.sql`: corrections table, unique index on `(extraction_id, revision, field_path)`.
3. `0009_extractions_unique_document.sql`: only after the duplicate-rows query comes back clean.

The grounding column from §3 gets the next free number when that phase is released from the hold.

### 8.5 Status of the safe phases (2026-10-09)

Built on `origin/dev` after PR #28 (pr27 merged). Nothing here changes extraction output.

- **(a) Evaluation harness:** `backend/eval/` (done).
- **(b) Cache:** `app/services/extraction_cache.py`, `migrations/0007_extraction_cache.sql`. **Off until you apply 0007 and set `EXTRACTION_CACHE_ENABLED=true`.** `force_refresh` on upload plus an "Ignore saved results" checkbox; a reused result is marked in `validation_errors` and shown as a "Saved result" badge. Force-refresh on `/process` for an *existing* extraction is not built: it needs the replace-and-archive step and is left for when you want it.
- **(c) Variance test:** `eval/variance.py`.
- **(d) Corrections:** `app/services/corrections_service.py`, `migrations/0008_extraction_corrections.sql`, `eval/export_corrections.py`, page-text edits recorded too, optional "why changed" per edited field. Recording happens *after* the review save and never blocks it (section 4.2 said before; changed so a missing table can't stop a lawyer saving). `human_correction` is unchanged (still a full copy); the table is the real record. The context columns for `pipeline_version` and `source` are not stored yet because that needs new columns on `extractions` before the code writes them.
- **Save-path fixes from 8.3:** a review update that changes no row now returns 409 instead of success and no longer moves the document's status; the extraction lookup is ordered by `id` so GET and PATCH always pick the same row; the saved extraction is written into the page's cache on success. `migrations/0009_extractions_unique_document.sql` is written but must wait for the duplicate-rows query; the pipeline now treats a lost insert race as "already processed" instead of flagging a good document.
- **Migration apply order:** `0007`, `0008`, then `0009` only if the duplicate query is clean.

