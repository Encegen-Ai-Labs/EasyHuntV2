"""Console and Markdown rendering of an evaluation run."""

from __future__ import annotations

from typing import Any, Dict, List

from .scorers import CORRECT, OUTCOMES, SCORED_FIELDS
from .summary import ALL


def _pct(v) -> str:
    return "  -  " if v is None else f"{v * 100:5.1f}"


def _field_table(cells: Dict[str, Any], doc_type: str = ALL) -> List[str]:
    lines = [f"{'field':<22}{'n':>3}  {'ok':>3} {'close':>5} {'wrong':>5} {'miss':>4} {'spur':>4}  {'strict':>6} {'lenient':>7}"]
    fields = list(SCORED_FIELDS) + sorted(
        k.split("|", 1)[1] for k in cells if k.startswith(f"{doc_type}|chain.")
    )
    for f in fields:
        c = cells.get(f"{doc_type}|{f}")
        if not c:
            continue
        k = c["counts"]
        lines.append(
            f"{f:<22}{c['n']:>3}  {k['correct']:>3} {k['close']:>5} {k['wrong']:>5} {k['missing']:>4} {k['spurious']:>4}"
            f"  {_pct(c['strict']):>6} {_pct(c['lenient']):>7}"
        )
    return lines


def render_text(agg: Dict[str, Any], title: str, runs: int, case_ids: List[str]) -> str:
    out = [title, f"cases: {len(case_ids)}   runs: {runs}", ""]
    h, c = agg.get("headline"), agg.get("critical")
    if h:
        out.append(f"headline (macro over {h['fields']} fields): strict {_pct(h['strict'])}  lenient {_pct(h['lenient'])}")
    if c:
        out.append(f"critical fields ({c['fields']}):           strict {_pct(c['strict'])}  lenient {_pct(c['lenient'])}")
    out += ["", "ALL document types", *_field_table(agg["cells"])]

    types = sorted({k.split("|", 1)[0] for k in agg["cells"]} - {ALL})
    for t in types:
        out += ["", f"document_type = {t}", *_field_table(agg["cells"], t)]

    for label, key in (("handwriting", "by_handwriting"), ("language", "by_language"), ("source", "by_source")):
        if agg.get(key):
            out += ["", f"by {label} (all scored fields pooled)"]
            for name, s in agg[key].items():
                out.append(f"  {name:<14} n={s['n']:<4} strict {_pct(s['strict'])}  lenient {_pct(s['lenient'])}")
    if agg.get("translit_form"):
        out += ["", "name fields compared in transliterated form (reported separately, not extraction errors)"]
        for name, s in agg["translit_form"].items():
            out.append(f"  {name:<22} n={s['n']:<4} strict {_pct(s['strict'])}  lenient {_pct(s['lenient'])}")
    if agg.get("notes"):
        out += ["", "error classes"]
        out += [f"  {k}: {v}" for k, v in agg["notes"].items()]
    return "\n".join(out)


def render_comparison(cmp: Dict[str, Any]) -> str:
    out: List[str] = []
    cd = cmp["case_diff"]
    if cd["only_in_baseline"] or cd["only_in_current"]:
        out.append(f"case sets differ: only in baseline {cd['only_in_baseline']}, only in current {cd['only_in_current']}")
    if cmp["missing_cells"]:
        out.append(f"cells in the baseline but not in this run: {cmp['missing_cells']}")
    if cmp["regressions"]:
        out.append(f"REGRESSIONS ({len(cmp['regressions'])}): a score is lower than the baseline")
        for r in cmp["regressions"]:
            tag = " (still within the baseline's own run-to-run spread)" if r["within_baseline_spread"] else ""
            out.append(f"  {r['cell']:<40} {r['metric']:<8} {_pct(r['baseline'])} -> {_pct(r['current'])}  n={r['n']}{tag}")
    else:
        out.append("no regressions against the baseline")
    if cmp["improvements"]:
        out.append(f"improvements: {len(cmp['improvements'])}")
    return "\n".join(out)


def render_markdown(text_report: str, rows: List[Dict[str, Any]], comparison: str = "") -> str:
    md = ["# Evaluation run", "", "```", text_report, "```", ""]
    if comparison:
        md += ["## Baseline comparison", "", "```", comparison, "```", ""]
    md += ["## Mismatches", ""]
    bad = [r for r in rows if r["outcome"] != CORRECT]
    if not bad:
        md.append("None.")
    last = None
    for r in sorted(bad, key=lambda r: (r["case_id"], r["field"])):
        if r["case_id"] != last:
            md += ["", f"### {r['case_id']} ({r['document_type']})", ""]
            md += ["| field | outcome | expected | got |", "|---|---|---|---|"]
            last = r["case_id"]
        e = str(r.get("expected")).replace("|", "\\|").replace("\n", " ")
        g = str(r.get("predicted")).replace("|", "\\|").replace("\n", " ")
        note = f" ({r['note']})" if r.get("note") else ""
        md.append(f"| {r['field']} | {r['outcome']}{note} | {e[:80]} | {g[:80]} |")
    return "\n".join(md) + "\n"
