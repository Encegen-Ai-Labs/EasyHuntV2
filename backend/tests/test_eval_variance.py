import json

import pytest

from eval import variance
from eval.live import LiveDeps


def run(**over):
    base = {"owner_name": "Ramesh Patil", "survey_number": "45/2B", "transaction_date": "1998-03-12",
            "owner_name_confidence": "high", "overall_confidence": "high", "has_handwritten_content": False,
            "full_text": "line one\nline two", "chain": [{"order": 1, "owner": "A", "date": "1990-01-01", "type": "Sale"}],
            "red_flags": [], "_meta": {"source": "vlm", "page_sources": ["vlm"]}}
    base.update(over)
    return base


def test_identical_runs_are_stable():
    r = variance.analyze([run(), run(), run()])
    assert all(e["verdict"] == "stable" for e in r["fields"].values())
    assert r["transcription"]["identical_in_all_runs"] and r["routing"]["stable"]
    assert "agreed in every run" in r["diagnosis"]


def test_cosmetic_difference_is_not_unstable():
    r = variance.analyze([run(owner_name="Ramesh Patil"), run(owner_name="Ramesh Patil."), run(owner_name="ramesh  patil")])
    e = r["fields"]["owner_name"]
    assert (e["distinct_raw"], e["distinct_norm"], e["verdict"]) == (3, 1, "cosmetic")


def test_real_difference_is_unstable_with_modal_share_and_similarity():
    r = variance.analyze([run(survey_number="45/2B"), run(survey_number="45/2B"), run(survey_number="45/28")])
    e = r["fields"]["survey_number"]
    assert e["verdict"] == "unstable" and e["modal_value"] == "45/2B"
    assert e["modal_share"] == pytest.approx(2 / 3) and e["min_pairwise_similarity"] < 1.0


def test_chain_and_red_flag_differences_are_detected():
    other_chain = [{"order": 1, "owner": "A", "date": "1991-01-01", "type": "Sale"}]
    r = variance.analyze([run(), run(chain=other_chain, red_flags=[{"type": "dispute", "severity": "high"}])])
    assert r["fields"]["chain"]["verdict"] == "unstable"
    assert r["fields"]["red_flags"]["verdict"] == "unstable"


def test_diagnosis_separates_the_two_stages():
    same_text = variance.analyze([run(survey_number="1"), run(survey_number="2")])
    assert "field-extraction call" in same_text["diagnosis"]
    diff_text = variance.analyze([run(survey_number="1", full_text="a\nb"), run(survey_number="2", full_text="a\nc")])
    assert "transcription itself differs" in diff_text["diagnosis"]
    assert diff_text["transcription"]["min_similarity_to_first_run"] < 1.0


def test_routing_change_is_reported():
    r = variance.analyze([run(), run(_meta={"source": "ocr", "page_sources": ["ocr"]})])
    assert r["routing"]["stable"] is False


def test_failed_runs_are_counted_and_excluded():
    r = variance.analyze([run(), {"_error": "504"}, run()])
    assert (r["runs"], r["failed_runs"]) == (3, 1)
    assert r["fields"]["owner_name"]["verdict"] == "stable"
    assert variance.analyze([{"_error": "x"}])["fields"] == {}


def test_render_mentions_verdicts_and_diagnosis():
    text = variance.render("doc", variance.analyze([run(survey_number="1"), run(survey_number="2")]), gemini_calls=4)
    assert "unstable" in text and "Gemini calls made: 4" in text and "diagnosis:" in text


def write_runs(tmp_path, per_run):
    for i, extraction in enumerate(per_run, 1):
        d = tmp_path / f"run_{i}"
        d.mkdir(parents=True)
        (d / "doc1.json").write_text(json.dumps(extraction), encoding="utf-8")
    return tmp_path


def test_cli_offline_from_recorded_runs(tmp_path, capsys):
    preds = write_runs(tmp_path / "p", [run(survey_number="1"), run(survey_number="2")])
    out = tmp_path / "out"
    assert variance.main(["--predictions", str(preds), "--out", str(out)]) == 0
    assert "survey_number" in capsys.readouterr().out
    saved = json.loads((out / "variance.json").read_text(encoding="utf-8"))
    assert saved["doc1"]["fields"]["survey_number"]["verdict"] == "unstable"
    assert variance.main(["--predictions", str(preds), "--case", "missing"]) == 2
    assert variance.main([]) == 2


def fake_deps(answers):
    """answers: list of owner names returned by successive field calls."""
    it = iter(answers)
    deps = LiveDeps(
        rasterize=lambda b, m: [b"p1", b"p2"],
        enhance=lambda img: (img, {}),
        route=lambda img, page_number, also_extract_fields: {
            "page_number": page_number, "original_text": f"text {page_number}", "source": "vlm",
            "has_handwriting": False, "structured_fields": None},
        extract_fields=lambda text: {"success": True, "extracted": {"owner_name": next(it)}},
        strip_tags=lambda t: t,
    )
    return deps


def test_cli_live_document_counts_calls_with_fake_deps(tmp_path, capsys):
    doc = tmp_path / "deed.pdf"
    doc.write_bytes(b"%PDF fake")
    code = variance.main(["--document", str(doc), "--n", "3", "--out", str(tmp_path / "o")],
                         deps=fake_deps(["Ramesh", "Ramesh", "Suresh"]))
    assert code == 0
    out = capsys.readouterr().out
    # 3 runs x (2 VLM pages + 1 field call) = 9 Gemini calls
    assert "Gemini calls made: 9" in out
    assert "owner_name" in out and "unstable" in out
    assert (tmp_path / "o" / "run_3" / "deed.json").exists()
    assert json.loads((tmp_path / "o" / "variance.json").read_text(encoding="utf-8"))["deed"]["gemini_calls"] == 9
