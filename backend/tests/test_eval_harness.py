import copy
import json
import shutil
from pathlib import Path

import pytest

from eval import live, loader, run, summary
from eval.loader import EvalDataError

EXAMPLE = Path(__file__).resolve().parents[1] / "eval" / "example"
EXAMPLE_PRED = EXAMPLE / "predictions" / "0000_example_sale_deed.json"


def make_data(tmp_path, cases):
    """cases: {id: split}. Each case is a copy of the synthetic example."""
    base = EXAMPLE / "cases" / "0000_example_sale_deed"
    for cid, split in cases.items():
        d = tmp_path / "cases" / cid
        shutil.copytree(base, d)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        meta.update(id=cid, split=split)
        (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return tmp_path


def make_preds(tmp_path, ids, mutate=None, name="preds"):
    pred = json.loads(EXAMPLE_PRED.read_text(encoding="utf-8"))
    d = tmp_path / name
    d.mkdir(exist_ok=True)
    for cid in ids:
        p = copy.deepcopy(pred)
        if mutate:
            mutate(cid, p)
        (d / f"{cid}.json").write_text(json.dumps(p), encoding="utf-8")
    return d


def cli(data, preds, out, *extra):
    return run.main(["--data-dir", str(data), "--predictions", str(preds), "--out", str(out), *extra])


def test_example_runs_end_to_end(tmp_path, capsys):
    code = cli(EXAMPLE, EXAMPLE / "predictions", tmp_path / "out")
    assert code == 0
    results = json.loads((tmp_path / "out" / "results.json").read_text(encoding="utf-8"))
    cell = results["cells"]["ALL|transaction_date"]
    assert cell["strict"] == 0.0 and cell["n"] == 1
    assert (tmp_path / "out" / "report.md").exists()
    assert "day_month_swap" in capsys.readouterr().out


def test_loader_rejects_unlabelled_field_silently_dropped(tmp_path):
    data = make_data(tmp_path / "d", {"c1": "holdout"})
    p = data / "cases" / "c1" / "expected.json"
    exp = json.loads(p.read_text(encoding="utf-8"))
    del exp["fields"]["area"]
    p.write_text(json.dumps(exp), encoding="utf-8")
    with pytest.raises(EvalDataError, match="area"):
        loader.load_cases(data)


def test_loader_rejects_bad_split_and_id_mismatch(tmp_path):
    data = make_data(tmp_path / "d", {"c1": "holdout"})
    meta_p = data / "cases" / "c1" / "meta.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8"))
    meta["split"] = "train"
    meta_p.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(EvalDataError, match="split"):
        loader.load_cases(data)
    meta.update(split="holdout", id="other")
    meta_p.write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(EvalDataError, match="folder name"):
        loader.load_cases(data)


def test_split_filtering_and_default_is_holdout(tmp_path):
    data = make_data(tmp_path / "d", {"a": "holdout", "b": "example"})
    assert [c.id for c in loader.load_cases(data)] == ["a"]
    assert [c.id for c in loader.load_cases(data, "example")] == ["b"]
    assert [c.id for c in loader.load_cases(data, "all")] == ["a", "b"]


def test_same_source_in_both_splits_is_an_error(tmp_path):
    data = make_data(tmp_path / "d", {"a": "holdout", "b": "example"})
    for cid in ("a", "b"):
        (data / "cases" / cid / "source.png").write_bytes(b"identical bytes")
    with pytest.raises(EvalDataError, match="leak"):
        loader.load_cases(data, "all")


def test_missing_prediction_is_an_error_not_a_zero(tmp_path, capsys):
    data = make_data(tmp_path / "d", {"a": "holdout", "b": "holdout"})
    preds = make_preds(tmp_path, ["a"])
    assert cli(data, preds, tmp_path / "o") == 2
    assert "no prediction file" in capsys.readouterr().err


def test_compare_exit_codes(tmp_path):
    data = make_data(tmp_path / "d", {"a": "holdout"})
    good = make_preds(tmp_path, ["a"], name="good")
    base = tmp_path / "baseline.json"
    assert cli(data, good, tmp_path / "o1", "--write-baseline", str(base)) == 0

    # identical run: no regression
    assert cli(data, good, tmp_path / "o2", "--compare", str(base)) == 0

    # an improvement is not a regression
    def fix(cid, p):
        p["transaction_date"] = "1998-03-12"
    better = make_preds(tmp_path, ["a"], fix, name="better")
    assert cli(data, better, tmp_path / "o3", "--compare", str(base)) == 0

    # lowering one field (owner_name was correct) exits 1
    def break_owner(cid, p):
        p["owner_name"] = "Somebody Else"
    worse = make_preds(tmp_path, ["a"], break_owner, name="worse")
    assert cli(data, worse, tmp_path / "o4", "--compare", str(base)) == 1


def test_compare_lenient_only_drop_is_a_regression(tmp_path):
    data = make_data(tmp_path / "d", {"a": "holdout"})
    good = make_preds(tmp_path, ["a"], name="good")
    base = tmp_path / "baseline.json"
    cli(data, good, tmp_path / "o1", "--write-baseline", str(base))

    def to_wrong(cid, p):  # previous_owner_name was 'close'; now wrong, so lenient drops
        p["previous_owner_name"] = "Totally Different"
    worse = make_preds(tmp_path, ["a"], to_wrong, name="worse")
    assert cli(data, worse, tmp_path / "o2", "--compare", str(base)) == 1


def test_compare_refuses_different_case_set(tmp_path):
    data1 = make_data(tmp_path / "d1", {"a": "holdout"})
    p1 = make_preds(tmp_path, ["a"], name="p1")
    base = tmp_path / "baseline.json"
    cli(data1, p1, tmp_path / "o1", "--write-baseline", str(base))
    data2 = make_data(tmp_path / "d2", {"a": "holdout", "b": "holdout"})
    p2 = make_preds(tmp_path, ["a", "b"], name="p2")
    assert cli(data2, p2, tmp_path / "o2", "--compare", str(base)) == 2
    assert cli(data2, p2, tmp_path / "o3", "--compare", str(base), "--allow-different-cases") == 0


def test_multiple_runs_average_and_record_spread(tmp_path):
    data = make_data(tmp_path / "d", {"a": "holdout"})
    preds = tmp_path / "preds"
    for k, owner in ((1, "Ramesh Kumar Patil"), (2, "Somebody Else")):
        d = preds / f"run_{k}"
        d.mkdir(parents=True)
        pred = json.loads(EXAMPLE_PRED.read_text(encoding="utf-8"))
        pred["owner_name"] = owner
        (d / "a.json").write_text(json.dumps(pred), encoding="utf-8")
    base = tmp_path / "baseline.json"
    assert cli(data, preds, tmp_path / "o", "--write-baseline", str(base)) == 0
    cell = json.loads(base.read_text(encoding="utf-8"))["cells"]["ALL|owner_name"]
    assert cell["strict"] == 0.5 and cell["strict_min"] == 0.0 and cell["strict_max"] == 1.0


def test_compare_marks_regression_inside_baseline_spread():
    baseline = summary.make_baseline(
        {"ALL|owner_name": {"n": 1, "strict": 0.5, "lenient": 0.5, "strict_min": 0.0, "strict_max": 1.0}},
        ["a"], 2, "now")
    cur = {"ALL|owner_name": {"n": 1, "strict": 0.0, "lenient": 0.5}}
    cmp = summary.compare(baseline, cur, ["a"])
    assert len(cmp["regressions"]) == 1 and cmp["regressions"][0]["within_baseline_spread"] is True


def test_live_and_predictions_are_mutually_exclusive(tmp_path):
    assert run.main(["--data-dir", str(EXAMPLE)]) == 2
    assert run.main(["--data-dir", str(EXAMPLE), "--live", "--predictions", str(tmp_path)]) == 2


# ------------------------------------------------------------ live (fakes)

def fake_deps(pages=1, vlm=True, fields_ok=True):
    calls = {"fields": [], "route_args": []}

    def route(img, page_number, also_extract_fields):
        calls["route_args"].append(also_extract_fields)
        return {"page_number": page_number, "original_text": f"text{page_number} [Stamp: X]",
                "source": "vlm" if vlm else "ocr", "has_handwriting": page_number == 2,
                "structured_fields": {"owner_name": "Combined"} if also_extract_fields and vlm else None}

    def extract_fields(text):
        calls["fields"].append(text)
        if not fields_ok:
            return {"success": False, "error": "boom", "extracted": None}
        return {"success": True, "extracted": {"owner_name": "FromText"}}

    deps = live.LiveDeps(
        rasterize=lambda b, m: [b"p"] * pages,
        enhance=lambda img: (img, {}),
        route=route, extract_fields=extract_fields,
        strip_tags=lambda t: t.replace("[Stamp: X]", ""),
    )
    return deps, calls


def case_with_source(tmp_path):
    data = make_data(tmp_path, {"a": "holdout"})
    (data / "cases" / "a" / "source.pdf").write_bytes(b"%PDF fake")
    (data / "cases" / "a" / "transcript.txt").write_text("gold text [Stamp: X]", encoding="utf-8")
    return loader.load_cases(data)[0]


def test_live_single_page_reuses_combined_fields(tmp_path):
    case = case_with_source(tmp_path)
    deps, calls = fake_deps(pages=1)
    out = live.extract_case(case, "end-to-end", deps)
    assert out["owner_name"] == "Combined" and calls["fields"] == [] and calls["route_args"] == [True]
    assert out["_meta"]["source"] == "vlm" and out["has_handwritten_content"] is False


def test_live_multi_page_merges_and_extracts_from_stripped_text(tmp_path):
    case = case_with_source(tmp_path)
    deps, calls = fake_deps(pages=2)
    out = live.extract_case(case, "end-to-end", deps)
    assert out["owner_name"] == "FromText"
    assert "[Stamp" not in calls["fields"][0] and "--- Page 2 ---" in calls["fields"][0]
    assert "--- Page 1 ---" in out["full_text"] and "[Stamp: X]" in out["full_text"]
    assert out["has_handwritten_content"] is True  # page 2 flagged


def test_live_fields_only_uses_transcript_and_failures_become_errors(tmp_path):
    case = case_with_source(tmp_path)
    deps, calls = fake_deps()
    out = live.extract_case(case, "fields-only", deps)
    assert out["owner_name"] == "FromText" and calls["route_args"] == []
    deps, _ = fake_deps(pages=2, fields_ok=False)
    assert live.extract_case(case, "end-to-end", deps) == {"_error": "boom"}
