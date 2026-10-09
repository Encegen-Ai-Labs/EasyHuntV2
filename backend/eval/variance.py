"""Variance test: does the same document give the same extraction every time?

  python -m eval.variance --predictions <dir> [--case <id>]
      Offline. <dir> is the layout eval.run uses: run_1/<case_id>.json,
      run_2/... (e.g. produced by `python -m eval.run --live --runs 5`).
      Reports, per document and per field, how many distinct answers came
      back and which one was most common.

  python -m eval.variance --document <file> --n 10
      Live. Runs the current extraction on one file N times (needs
      GEMINI_API_KEY and makes real Gemini calls; no cache is involved) and
      then reports as above, including how many Gemini calls it made.

For each document it also says where the instability starts:
  * transcription identical in every run but fields differ -> the field
    extraction call is varying;
  * transcription differs between runs -> the page reading is varying (and
    that carries into the fields).

"distinct (raw)" counts exact differences; "distinct (norm)" ignores case,
punctuation, spacing and digit script, so a cosmetic difference (a trailing
full stop) is not mistaken for a real one.
"""

from __future__ import annotations

import argparse
import difflib
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional

from .normalize import norm_text, ratio
from .scorers import SCALAR_FIELDS

CONFIDENCE_FIELDS = tuple(f"{f}_confidence" for f in ("owner_name", "previous_owner_name", "survey_number", "transaction_date"))
EXTRA_SCALARS = ("overall_confidence", "has_handwritten_content")
LIST_FIELDS = ("chain", "red_flags")
TRACKED = SCALAR_FIELDS + CONFIDENCE_FIELDS + EXTRA_SCALARS + LIST_FIELDS
TEXT_FIELDS = {"owner_name", "previous_owner_name", "survey_number", "property_location",
               "property_boundaries", "area", "registration_number", "language_detected"}


def _raw(field: str, value: Any) -> str:
    if field == "chain":
        links = [l for l in (value or []) if isinstance(l, dict)]
        return json.dumps([[l.get("order"), l.get("owner"), l.get("date"), l.get("type"), l.get("survey")] for l in links],
                          ensure_ascii=False)
    if field == "red_flags":
        flags = [f for f in (value or []) if isinstance(f, dict)]
        return json.dumps(sorted((f.get("type") or "other", f.get("severity") or "") for f in flags), ensure_ascii=False)
    return json.dumps(value, ensure_ascii=False)


def _norm(field: str, value: Any) -> str:
    if field == "chain":
        links = [l for l in (value or []) if isinstance(l, dict)]
        return json.dumps([[l.get("order"), norm_text(l.get("owner") or ""), l.get("date"),
                            norm_text(l.get("type") or ""), norm_text(str(l.get("survey") or ""))] for l in links],
                          ensure_ascii=False)
    if field == "red_flags":
        return json.dumps(sorted(norm_text(f.get("type") or "other") for f in (value or []) if isinstance(f, dict)))
    if isinstance(value, str):
        return norm_text(value)
    return json.dumps(value, ensure_ascii=False)


def _line_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.splitlines(), b.splitlines(), autojunk=False).ratio()


def analyze(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """runs: extraction dicts for ONE document, one per run. Runs that failed
    (`_error`) are counted and left out of the field statistics."""
    ok = [r for r in runs if "_error" not in r]
    out: Dict[str, Any] = {"runs": len(runs), "failed_runs": len(runs) - len(ok), "fields": {}, "transcription": None}
    if not ok:
        return out

    for f in TRACKED:
        raws = [_raw(f, r.get(f)) for r in ok]
        norms = [_norm(f, r.get(f)) for r in ok]
        counts = Counter(raws)
        modal_raw, modal_n = counts.most_common(1)[0]
        entry: Dict[str, Any] = {
            "distinct_raw": len(counts),
            "distinct_norm": len(set(norms)),
            "modal_share": modal_n / len(ok),
            "modal_value": json.loads(modal_raw),
            "values": {k: v for k, v in counts.most_common()},
        }
        if f in TEXT_FIELDS:
            strs = [str(r.get(f)) for r in ok if r.get(f) not in (None, "")]
            sims = [ratio(norm_text(a), norm_text(b)) for i, a in enumerate(strs) for b in strs[i + 1:]]
            entry["min_pairwise_similarity"] = min(sims) if sims else None
        entry["verdict"] = (
            "stable" if entry["distinct_raw"] == 1
            else "cosmetic" if entry["distinct_norm"] == 1
            else "unstable"
        )
        out["fields"][f] = entry

    texts = [r.get("full_text") for r in ok if isinstance(r.get("full_text"), str)]
    if texts:
        sims = [_line_similarity(texts[0], t) for t in texts[1:]]
        identical = len(set(texts)) == 1
        out["transcription"] = {
            "identical_in_all_runs": identical,
            "distinct": len(set(texts)),
            "min_similarity_to_first_run": min(sims) if sims else 1.0,
            "mean_similarity_to_first_run": (sum(sims) / len(sims)) if sims else 1.0,
        }
    sources = [json.dumps((r.get("_meta") or {}).get("page_sources", (r.get("_meta") or {}).get("source"))) for r in ok]
    out["routing"] = {"distinct": len(set(sources)), "stable": len(set(sources)) == 1}

    unstable = [f for f, e in out["fields"].items() if e["verdict"] == "unstable"]
    t = out["transcription"]
    if not unstable:
        out["diagnosis"] = "All tracked fields agreed in every run (after ignoring cosmetic differences)."
    elif t and t["identical_in_all_runs"]:
        out["diagnosis"] = ("The transcription was identical in every run but fields differ: the instability is in the "
                            "field-extraction call, not in reading the page.")
    elif t:
        out["diagnosis"] = ("The transcription itself differs between runs, so the page reading varies and carries into "
                            "the fields. Field-call variance cannot be separated from it here.")
    else:
        out["diagnosis"] = "No transcription was recorded, so the source of the instability cannot be attributed to a stage."
    return out


def render(name: str, result: Dict[str, Any], gemini_calls: Optional[int] = None) -> str:
    lines = [f"{name}: {result['runs']} runs" + (f", {result['failed_runs']} failed" if result["failed_runs"] else "")]
    if gemini_calls is not None:
        lines.append(f"  Gemini calls made: {gemini_calls}")
    if not result["fields"]:
        return "\n".join(lines + ["  no successful runs"])
    lines.append(f"  {'field':<24}{'verdict':<10}{'raw':>4}{'norm':>5}{'modal':>7}  {'minsim':>6}  most common value")
    for f, e in result["fields"].items():
        sim = e.get("min_pairwise_similarity")
        shown = str(e["modal_value"])
        lines.append(
            f"  {f:<24}{e['verdict']:<10}{e['distinct_raw']:>4}{e['distinct_norm']:>5}{e['modal_share'] * 100:>6.0f}%"
            f"  {('%.2f' % sim) if sim is not None else '  -  ':>6}  {shown[:50]}"
        )
    t = result["transcription"]
    if t:
        lines.append(f"  transcription: {'identical in all runs' if t['identical_in_all_runs'] else str(t['distinct']) + ' distinct versions'}"
                     f" (line similarity to run 1: min {t['min_similarity_to_first_run']:.3f}, mean {t['mean_similarity_to_first_run']:.3f})")
    lines.append(f"  routing (OCR/VLM per page): {'same in every run' if result['routing']['stable'] else 'DIFFERED between runs'}")
    lines.append(f"  diagnosis: {result['diagnosis']}")
    return "\n".join(lines)


def load_runs(pred_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    run_dirs = sorted(d for d in pred_dir.iterdir() if d.is_dir() and d.name.startswith("run_"))
    if not run_dirs:
        raise SystemExit(f"no run_*/ folders in {pred_dir}")
    by_case: Dict[str, List[Dict[str, Any]]] = {}
    for d in run_dirs:
        for f in sorted(d.glob("*.json")):
            by_case.setdefault(f.stem, []).append(json.loads(f.read_text(encoding="utf-8")))
    return by_case


def _count_calls(deps, counter: Dict[str, int]):
    """Wraps LiveDeps so Gemini calls can be counted: every VLM-routed page
    is one call (a combined single-page call included), every field
    extraction from text is one."""
    from .live import LiveDeps
    route, fields = deps.route, deps.extract_fields

    def counted_route(*a, **k):
        r = route(*a, **k)
        if r.get("source") == "vlm":
            counter["calls"] += 1
        return r

    def counted_fields(text):
        counter["calls"] += 1
        return fields(text)

    return LiveDeps(rasterize=deps.rasterize, enhance=deps.enhance, route=counted_route,
                    extract_fields=counted_fields, strip_tags=deps.strip_tags)


def run_document(path: Path, n: int, deps=None) -> tuple:
    """Live: extracts one file n times. Returns (runs, gemini_calls)."""
    from . import live
    deps = deps or live.default_deps()
    counter = {"calls": 0}
    deps = _count_calls(deps, counter)
    case = SimpleNamespace(id=path.stem, source_path=path, transcript_path=None)
    runs = []
    for i in range(1, n + 1):
        print(f"run {i}/{n}", file=sys.stderr)
        runs.append(live.extract_case(case, "end-to-end", deps))
    return runs, counter["calls"]


def main(argv: Optional[List[str]] = None, deps=None) -> int:
    ap = argparse.ArgumentParser(prog="eval.variance", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--predictions", type=Path, help="folder of run_*/ recorded extractions")
    ap.add_argument("--case", help="only this case id (with --predictions)")
    ap.add_argument("--document", type=Path, help="live: a single source file to extract repeatedly")
    ap.add_argument("--n", type=int, default=10, help="live: number of runs")
    ap.add_argument("--out", type=Path, help="write the result JSON (and, live, the raw runs) here")
    args = ap.parse_args(argv)

    if bool(args.predictions) == bool(args.document):
        print("give exactly one of --predictions or --document", file=sys.stderr)
        return 2

    results: Dict[str, Any] = {}
    if args.predictions:
        by_case = load_runs(args.predictions)
        if args.case:
            if args.case not in by_case:
                print(f"error: no runs for case '{args.case}'", file=sys.stderr)
                return 2
            by_case = {args.case: by_case[args.case]}
        for name, runs in sorted(by_case.items()):
            results[name] = analyze(runs)
            print(render(name, results[name]) + "\n")
    else:
        if not args.document.exists():
            print(f"error: {args.document} not found", file=sys.stderr)
            return 2
        runs, calls = run_document(args.document, max(2, args.n), deps)
        results[args.document.stem] = analyze(runs)
        results[args.document.stem]["gemini_calls"] = calls
        print(render(args.document.stem, results[args.document.stem], calls))
        if args.out:
            args.out.mkdir(parents=True, exist_ok=True)
            for i, r in enumerate(runs, 1):
                d = args.out / f"run_{i}"
                d.mkdir(exist_ok=True)
                (d / f"{args.document.stem}.json").write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        (args.out / "variance.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
