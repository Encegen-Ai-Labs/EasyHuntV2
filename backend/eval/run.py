"""Score extractions against the corrected answers.

  python -m eval.run --predictions <dir>                 score recorded extractions (no API key)
  python -m eval.run --live [--stage fields-only]        run the current extraction first (needs GEMINI_API_KEY)
  python -m eval.run --predictions <dir> --write-baseline baseline.json
  python -m eval.run --predictions <dir> --compare baseline.json

Exit codes: 0 ok / no regression, 1 a score is lower than the baseline,
2 bad data, bad arguments, or a comparison that cannot be trusted.

--predictions layout: either <dir>/<case_id>.json (one run), or
<dir>/run_1/<case_id>.json, <dir>/run_2/... (several runs; scores are the
mean over runs, with the min/max recorded in the baseline).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import report, summary
from .loader import Case, EvalDataError, default_data_dir, load_cases
from .scorers import score_document


def _run_dirs(pred_dir: Path) -> List[Path]:
    runs = sorted(d for d in pred_dir.iterdir() if d.is_dir() and d.name.startswith("run_"))
    return runs or [pred_dir]


def _load_prediction(run_dir: Path, case_id: str) -> Optional[Dict[str, Any]]:
    path = run_dir / f"{case_id}.json"
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def score_run(cases: List[Case], run_dir: Path) -> List[Dict[str, Any]]:
    missing = [c.id for c in cases if not (run_dir / f"{c.id}.json").exists()]
    if missing:
        raise EvalDataError(f"no prediction file in {run_dir} for: {', '.join(missing)}")
    rows: List[Dict[str, Any]] = []
    for c in cases:
        pred = _load_prediction(run_dir, c.id) or {}
        meta = pred.get("_meta") or {}
        if "_error" in pred:
            print(f"  note: {c.id} extraction failed in this run: {pred['_error']}", file=sys.stderr)
        for item in score_document(c.expected, pred):
            rows.append({
                "case_id": c.id, "document_type": c.document_type,
                "handwriting": c.meta.get("handwriting"), "language": c.meta.get("language"),
                "source": meta.get("source"),
                "field": item.field, "outcome": item.outcome, "form": item.form,
                "note": item.note, "expected": item.expected, "predicted": item.predicted,
            })
    return rows


def _live(cases: List[Case], out_dir: Path, runs: int, stage: str) -> Path:
    from . import live  # lazy: keeps the offline path free of app imports
    deps = live.default_deps()
    pred_root = out_dir / "predictions"
    for k in range(1, runs + 1):
        run_dir = pred_root / f"run_{k}"
        run_dir.mkdir(parents=True, exist_ok=True)
        for c in cases:
            print(f"run {k}/{runs}: {c.id}", file=sys.stderr)
            result = live.extract_case(c, stage, deps)
            with open(run_dir / f"{c.id}.json", "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
    return pred_root


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="eval.run", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data-dir", type=Path, default=None, help="folder containing cases/ (default: $EVAL_DATA_DIR or <repo>/eval_data)")
    ap.add_argument("--split", default="holdout", choices=["holdout", "example", "all"],
                    help="holdout is the headline set; example documents are in the prompt and are not comparable")
    ap.add_argument("--predictions", type=Path, help="folder of recorded extractions to score")
    ap.add_argument("--live", action="store_true", help="run the current extraction on each source file first (needs GEMINI_API_KEY)")
    ap.add_argument("--runs", type=int, default=1, help="with --live: how many times to run each document")
    ap.add_argument("--stage", default="end-to-end", choices=["end-to-end", "fields-only"],
                    help="fields-only feeds transcript.txt to the field extractor, skipping OCR/VLM")
    ap.add_argument("--out", type=Path, default=None, help="where to write results (default: <repo>/eval_runs/<timestamp>)")
    ap.add_argument("--write-baseline", type=Path)
    ap.add_argument("--compare", type=Path, help="baseline.json; exit 1 if any score is lower")
    ap.add_argument("--allow-different-cases", action="store_true",
                    help="compare even though the set of documents differs from the baseline's")
    args = ap.parse_args(argv)

    if bool(args.live) == bool(args.predictions):
        print("give exactly one of --live or --predictions", file=sys.stderr)
        return 2
    if args.live and args.split != "holdout":
        print("--live only runs the holdout split", file=sys.stderr)
        return 2

    now = datetime.now()
    out_dir = args.out or Path(__file__).resolve().parents[2] / "eval_runs" / now.strftime("%Y%m%d-%H%M%S")
    try:
        cases = load_cases(args.data_dir or default_data_dir(), args.split)
        if not cases:
            raise EvalDataError(f"no cases in split '{args.split}'")
        if args.split in ("example", "all"):
            print("WARNING: example documents are in the prompt; their scores are contaminated and not comparable.", file=sys.stderr)
        out_dir.mkdir(parents=True, exist_ok=True)
        pred_root = _live(cases, out_dir, max(1, args.runs), args.stage) if args.live else args.predictions
        run_dirs = _run_dirs(pred_root)
        all_rows: List[List[Dict[str, Any]]] = [score_run(cases, d) for d in run_dirs]
    except EvalDataError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    per_run = [summary.aggregate(rows) for rows in all_rows]
    # Shown numbers pool every run's items (equal to the mean of the runs,
    # since each run scores the same items); the baseline and the comparison
    # use the per-run means with their min/max spread.
    agg = per_run[0] if len(per_run) == 1 else summary.aggregate([r for rows in all_rows for r in rows])
    cells = summary.combine_runs(per_run)
    case_ids = [c.id for c in cases]

    text = report.render_text(agg, "Extraction evaluation", len(run_dirs), case_ids)
    print(text)

    comparison_text = ""
    exit_code = 0
    if args.compare:
        try:
            with open(args.compare, encoding="utf-8") as f:
                baseline = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read baseline: {e}", file=sys.stderr)
            return 2
        cmp = summary.compare(baseline, cells, case_ids, args.allow_different_cases)
        comparison_text = report.render_comparison(cmp)
        print("\n" + comparison_text)
        if not cmp["comparable"] or cmp["missing_cells"]:
            print("error: this run is not comparable with the baseline", file=sys.stderr)
            exit_code = 2
        elif cmp["regressions"]:
            exit_code = 1

    summary.write_json(out_dir / "results.json", {
        "created": now.isoformat(timespec="seconds"), "split": args.split, "runs": len(run_dirs),
        "case_ids": case_ids, "headline": agg["headline"], "critical": agg["critical"],
        "cells": cells, "rows": all_rows[0] if len(all_rows) == 1 else all_rows,
    })
    (out_dir / "report.md").write_text(
        report.render_markdown(text, all_rows[0], comparison_text), encoding="utf-8")
    if args.write_baseline:
        summary.write_json(args.write_baseline, summary.make_baseline(
            cells, case_ids, len(run_dirs), now.isoformat(timespec="seconds")))
        print(f"\nbaseline written to {args.write_baseline}")
    print(f"\nresults in {out_dir}")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
