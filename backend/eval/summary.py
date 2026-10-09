"""Aggregation, baseline files and the regression comparison."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .scorers import CRITICAL_FIELDS, OUTCOMES, SCORED_FIELDS, CORRECT, CLOSE

BASELINE_VERSION = 1
EPS = 1e-9
ALL = "ALL"


def _scores(counts: Dict[str, int]) -> Dict[str, Any]:
    n = sum(counts.get(o, 0) for o in OUTCOMES)
    return {
        "n": n,
        "counts": {o: counts.get(o, 0) for o in OUTCOMES},
        "strict": (counts.get(CORRECT, 0) / n) if n else None,
        "lenient": ((counts.get(CORRECT, 0) + counts.get(CLOSE, 0)) / n) if n else None,
    }


def aggregate(rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """rows: one dict per scored item with keys case_id, document_type, field,
    outcome, form, handwriting, language, source.

    Returns cells keyed "<document_type>|<field>" (and "ALL|<field>"), plus
    breakdowns. Only top-level SCORED_FIELDS and chain.* detail rows appear
    in cells; the headline numbers use SCORED_FIELDS only."""
    cells: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_handwriting: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_language: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_source: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    by_form: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    notes: Dict[str, int] = defaultdict(int)
    for r in rows:
        f, o = r["field"], r["outcome"]
        cells[f"{r['document_type']}|{f}"][o] += 1
        cells[f"{ALL}|{f}"][o] += 1
        if f in SCORED_FIELDS:
            by_handwriting[r.get("handwriting") or "?"][o] += 1
            by_language[r.get("language") or "?"][o] += 1
            if r.get("source"):
                by_source[r["source"]][o] += 1
        if r.get("form") == "translit":
            by_form[f][o] += 1
        if r.get("note"):
            notes[f"{f}:{r['note']}"] += 1
    cell_scores = {k: _scores(v) for k, v in sorted(cells.items())}

    def macro(names: Tuple[str, ...]) -> Optional[Dict[str, Any]]:
        vals = [cell_scores[f"{ALL}|{n}"] for n in names if f"{ALL}|{n}" in cell_scores]
        strict = [v["strict"] for v in vals if v["strict"] is not None]
        lenient = [v["lenient"] for v in vals if v["lenient"] is not None]
        if not strict:
            return None
        return {"fields": len(strict), "strict": sum(strict) / len(strict), "lenient": sum(lenient) / len(lenient)}

    return {
        "cells": cell_scores,
        "headline": macro(SCORED_FIELDS),
        "critical": macro(CRITICAL_FIELDS),
        "by_handwriting": {k: _scores(v) for k, v in sorted(by_handwriting.items())},
        "by_language": {k: _scores(v) for k, v in sorted(by_language.items())},
        "by_source": {k: _scores(v) for k, v in sorted(by_source.items())},
        "translit_form": {k: _scores(v) for k, v in sorted(by_form.items())},
        "notes": dict(sorted(notes.items())),
    }


def combine_runs(per_run: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Mean (and min/max spread) of every cell's score across runs."""
    keys = sorted({k for run in per_run for k in run["cells"]})
    cells: Dict[str, Any] = {}
    for k in keys:
        s = [run["cells"][k]["strict"] for run in per_run if k in run["cells"] and run["cells"][k]["strict"] is not None]
        l = [run["cells"][k]["lenient"] for run in per_run if k in run["cells"] and run["cells"][k]["lenient"] is not None]
        n = max(run["cells"][k]["n"] for run in per_run if k in run["cells"])
        if not s:
            continue
        cells[k] = {
            "n": n, "strict": sum(s) / len(s), "lenient": sum(l) / len(l),
            "strict_min": min(s), "strict_max": max(s),
        }
    return cells


def make_baseline(cells: Dict[str, Any], case_ids: List[str], runs: int, created: str) -> Dict[str, Any]:
    return {"baseline_version": BASELINE_VERSION, "created": created, "runs": runs,
            "case_ids": sorted(case_ids), "cells": cells}


def write_json(path, obj) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def compare(baseline: Dict[str, Any], cells: Dict[str, Any], case_ids: List[str],
            allow_different_cases: bool = False) -> Dict[str, Any]:
    """Regression check. A *regression* is any cell whose strict or lenient
    score is lower than the baseline's. Returns {comparable, regressions,
    improvements, missing_cells, case_diff}."""
    case_diff = {
        "only_in_baseline": sorted(set(baseline["case_ids"]) - set(case_ids)),
        "only_in_current": sorted(set(case_ids) - set(baseline["case_ids"])),
    }
    comparable = allow_different_cases or not (case_diff["only_in_baseline"] or case_diff["only_in_current"])
    regressions, improvements, missing = [], [], []
    for key, base in baseline["cells"].items():
        cur = cells.get(key)
        if cur is None:
            missing.append(key)
            continue
        for metric in ("strict", "lenient"):
            delta = cur[metric] - base[metric]
            if delta < -EPS:
                regressions.append({
                    "cell": key, "metric": metric, "baseline": base[metric], "current": cur[metric],
                    "n": cur["n"],
                    "within_baseline_spread": metric == "strict" and cur[metric] >= base.get("strict_min", base[metric]) - EPS,
                })
            elif delta > EPS:
                improvements.append({"cell": key, "metric": metric, "baseline": base[metric], "current": cur[metric]})
    return {"comparable": comparable, "regressions": regressions, "improvements": improvements,
            "missing_cells": missing, "case_diff": case_diff}
