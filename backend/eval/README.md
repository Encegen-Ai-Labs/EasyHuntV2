# Extraction evaluation harness

Scores the extraction against lawyer-corrected answers. Design and rationale:
`docs/EXTRACTION_QUALITY.md` sections 1 and 8.

## Where the data goes

Real documents are client data. They live in `eval_data/` at the repo root
(gitignored), or anywhere else via `EVAL_DATA_DIR` / `--data-dir`:

```
eval_data/cases/<id>/
  source.pdf|png|jpg   the original upload, unmodified (only needed for --live)
  expected.json        correct answers (format: expected.schema.json)
  meta.json            id, document_type, split, handwriting, language, pages, notes
  transcript.txt       OPTIONAL correct full text; enables --stage fields-only
```

`example/` holds one synthetic case and a recorded prediction, so you can try
the scorer with no data and no API key:

```
cd backend
python -m eval.run --data-dir eval/example --predictions eval/example/predictions
```

## expected.json rules

- Key names are the extraction's own (`owner_name`, `transaction_date`, ...).
- `null` is an answer: the correct extraction is null. A value returned there
  is `spurious`.
- Every scalar field must be either in `fields` or listed in `unlabelled`.
  A field in neither is an error, so a typo cannot silently drop a field.
  `chain` and `red_flags` may simply be left out (= unlabelled).
- `alternates`: extra acceptable values for a field.
- `transliterations`: for name fields whose canonical value is in the
  document's script. A Latin-letter prediction is scored against the
  transliteration and reported in its own "transliterated form" block, apart
  from the main score.
- Dates are `YYYY-MM-DD`; `YYYY-01-01` when only the year is known.

## meta.json

`split` is `holdout` (scored, the headline) or `example` (will be used in the
prompt; never in the headline). The same source file in both splits is an
error. `handwriting` is `none|partial|full`.

## Running

Offline, on recorded extractions (one JSON per case, named `<case_id>.json`,
shaped like `validated_json_output`; optional `"_meta": {"source": "ocr|vlm"}`):

```
python -m eval.run --predictions <dir> [--split holdout|example|all]
```

`<dir>` may instead contain `run_1/`, `run_2/`, ... for several runs; the
score is then the mean over runs and the baseline records the min/max.

Live (makes real Gemini calls, needs `GEMINI_API_KEY`; no test runs it):

```
python -m eval.run --live [--runs 5] [--stage end-to-end|fields-only]
```

Live mode re-composes the pipeline steps without Supabase. That duplicates
the orchestration in `pipeline_service.py` until the DB-free core function in
the plan (section 1.5) exists; see the note at the top of `eval/live.py`.

## Baseline and the stop rule

```
python -m eval.run --predictions <dir> --write-baseline baseline.json
python -m eval.run --predictions <dir2> --compare baseline.json
```

Exit code 1 if any `(document_type, field)` cell has a strict or lenient score
lower than the baseline's (cells named `ALL|<field>` pool all types). Exit 2
if the run cannot be compared (different set of documents, cells missing, bad
files). A regression is annotated when it is still inside the baseline's own
run-to-run spread, but it still exits 1.

With a handful of documents one document moves a cell by a large step; read
the `n` next to every number.

## Outputs

`eval_runs/<timestamp>/` (gitignored): `results.json`, `report.md` (with a
per-document table of every mismatch), and `predictions/` for `--live`.

## Variance test

Does the same document give the same extraction every time?

```
python -m eval.variance --predictions <dir>        # offline, on run_1/, run_2/, ... recorded by eval.run --live --runs N
python -m eval.variance --document <file> --n 10   # live: needs GEMINI_API_KEY, makes real Gemini calls
```

Per field: distinct answers (raw, and after ignoring case/punctuation/digit
script), the most common answer and its share, and a verdict (`stable`,
`cosmetic`, `unstable`). It also says whether the page transcription itself
varied between runs or only the field extraction did, whether OCR/VLM routing
changed, and (live) how many Gemini calls were made. The extraction cache is
not involved: live mode calls the extraction steps directly.

## Growing the set from lawyer reviews

Every review save is recorded in `extraction_corrections` (append-only; see
`backend/migrations/0008_extraction_corrections.sql`). Approved documents can
be exported into this folder format, on your machine with your own
credentials:

```
python -m eval.export_corrections --all-approved --dry-run
python -m eval.export_corrections --document-id <uuid> [--split holdout|example]
```

Only fields a human touched (edited, cleared, or confirmed by approving) are
labelled; everything else goes under `unlabelled`, so an unreviewed model
guess is never taken for a correct answer. New cases default to `holdout`;
`handwriting` is a placeholder (`partial`/`none`) to correct by hand. Existing
case folders are never overwritten.

