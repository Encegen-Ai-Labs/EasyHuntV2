from eval import scorers as s
from eval.scorers import CLOSE, CORRECT, MISSING, SPURIOUS, WRONG


def one(name, expected, predicted, alternates=(), translit=None):
    return s.score_scalar(name, expected, list(alternates), predicted, translit)


def test_null_handling():
    assert one("owner_name", None, None).outcome == CORRECT
    assert one("owner_name", None, "").outcome == CORRECT
    assert one("owner_name", None, "Ramesh").outcome == SPURIOUS
    assert one("owner_name", "Ramesh Patil", None).outcome == MISSING
    assert one("owner_name", "Ramesh Patil", "  ").outcome == MISSING


def test_name_exact_ignores_honorific_case_punct_and_order():
    assert one("owner_name", "Ramesh Kumar Patil", "Shri. RAMESH  Kumar Patil").outcome == CORRECT
    assert one("owner_name", "Ramesh Kumar Patil", "Patil, Ramesh Kumar").outcome == CORRECT


def test_name_close_initials_and_spelling_but_not_bare_surname():
    assert one("owner_name", "Ramesh Kumar Patil", "Ramesh K. Patil").outcome == CLOSE
    assert one("owner_name", "Ramesh Kumar Patil", "Ramesh Kumar Patel").outcome == CLOSE
    assert one("owner_name", "Ramesh Kumar Patil", "Patil").outcome == WRONG
    assert one("owner_name", "Ramesh Kumar Patil", "Suresh Kumar Joshi").outcome == WRONG


def test_name_devanagari_and_alternates():
    assert one("owner_name", "रमेश कुमार पाटील", "श्री रमेश कुमार पाटील").outcome == CORRECT
    assert one("owner_name", "रमेश कुमार पाटील", "Ramesh Kumar Patil").outcome == WRONG
    assert one("owner_name", "रमेश कुमार पाटील", "Ramesh Patil", alternates=["Ramesh Patil"]).outcome == CORRECT


def test_transliteration_is_scored_as_its_own_form():
    item = one("owner_name", "रमेश कुमार पाटील", "Ramesh Kumar Patil", translit="Ramesh Kumar Patil")
    assert (item.outcome, item.form) == (CORRECT, "translit")
    item = one("owner_name", "रमेश कुमार पाटील", "रमेश कुमार पाटील", translit="Ramesh Kumar Patil")
    assert (item.outcome, item.form) == (CORRECT, "script")
    item = one("owner_name", "रमेश कुमार पाटील", "Suresh Joshi", translit="Ramesh Kumar Patil")
    assert (item.outcome, item.form) == (WRONG, "translit")


def test_identifier():
    assert one("survey_number", "45/2B", "45 / 2b").outcome == CORRECT
    assert one("survey_number", "45/2B", "Gat No. 45/2B").outcome == CLOSE
    assert one("survey_number", "45/2B", "45/2C").outcome == WRONG
    assert one("survey_number", "१२३", "123").outcome == CORRECT  # Devanagari digits
    assert one("registration_number", "1234/1998", "S.No. 1234/1998").outcome == CLOSE


def test_date_exact_and_day_month_swap_is_flagged():
    assert one("transaction_date", "1998-03-12", "1998-03-12").outcome == CORRECT
    swapped = one("transaction_date", "1998-03-12", "1998-12-03")
    assert (swapped.outcome, swapped.note) == (WRONG, "day_month_swap")
    other = one("transaction_date", "1998-03-12", "1999-03-12")
    assert (other.outcome, other.note) == (WRONG, None)


def test_area_units_synonyms_and_tolerance():
    assert one("area", "2 Acre 10 Gunthas", "2 acres 10 guntha").outcome == CORRECT
    assert one("area", "1200 sq ft", "1200 square feet").outcome == CORRECT
    assert one("area", "1000 sq m", "1003 sqm").outcome == CLOSE
    assert one("area", "1000 sq m", "1200 sqm").outcome == WRONG
    assert one("area", "1 acre", "1 hectare").outcome == WRONG


def test_enum_and_language():
    assert one("document_type", "sale_deed", "Sale Deed").outcome == CORRECT
    assert one("document_type", "sale_deed", "gift_deed").outcome == WRONG
    assert one("language_detected", "Marathi", "mr").outcome == CORRECT


def test_freetext_close_by_token_f1():
    exp = "Village Wagholi, Tal. Haveli, Dist. Pune"
    assert one("property_location", exp, "village wagholi tal haveli dist pune").outcome == CORRECT
    assert one("property_location", exp, "Wagholi, Tal. Haveli, Dist. Pune").outcome == CLOSE
    assert one("property_location", exp, "Nashik").outcome == WRONG


CHAIN = [
    {"order": 1, "owner": "Sunil Patil", "date": "1975-06-01", "type": "Inheritance"},
    {"order": 2, "owner": "Ramesh Patil", "date": "1998-03-12", "type": "Sale Deed"},
]


def agg(items):
    return next(i for i in items if i.field == "chain")


def test_chain_correct_and_wrong_date():
    assert agg(s.score_chain(CHAIN, [dict(l) for l in CHAIN])).outcome == CORRECT
    bad = [dict(l) for l in CHAIN]
    bad[1]["date"] = "1999-03-12"
    items = s.score_chain(CHAIN, bad)
    assert agg(items).outcome == WRONG
    assert [i.outcome for i in items if i.field == "chain.date"] == [CORRECT, WRONG]


def test_chain_length_empty_and_missing():
    assert agg(s.score_chain(CHAIN, CHAIN[:1])).outcome == WRONG
    assert agg(s.score_chain(CHAIN, None)).outcome == MISSING
    assert agg(s.score_chain([], CHAIN)).outcome == SPURIOUS
    assert agg(s.score_chain([], [])).outcome == CORRECT
    items = s.score_chain(CHAIN, CHAIN[:1])
    assert [i.outcome for i in items if i.field == "chain.owner"] == [CORRECT, MISSING]


def test_chain_close_when_names_are_close():
    pred = [dict(l) for l in CHAIN]
    pred[1]["owner"] = "Ramesh K. Patil"
    exp = [dict(l) for l in CHAIN]
    exp[1]["owner"] = "Ramesh Kumar Patil"
    assert agg(s.score_chain(exp, pred)).outcome == CLOSE


def test_red_flags_match_by_type_and_quote():
    exp = [{"type": "encumbrance", "source_text": "mortgaged to the Co-op Bank"}]
    ok = s.score_red_flags(exp, [{"type": "encumbrance", "source_text": "property mortgaged to Co-op Bank"}])
    assert [i.outcome for i in ok] == [CORRECT]
    wrong_type = s.score_red_flags(exp, [{"type": "dispute", "source_text": "mortgaged to the Co-op Bank"}])
    assert sorted(i.outcome for i in wrong_type) == [MISSING, SPURIOUS]
    assert [i.outcome for i in s.score_red_flags([], [])] == []
    assert [i.outcome for i in s.score_red_flags([], [{"type": "other"}])] == [SPURIOUS]


def test_score_document_skips_unlabelled_and_scores_labelled_null():
    doc = {
        "fields": {f: None for f in s.SCALAR_FIELDS if f != "owner_name"},
        "unlabelled": ["owner_name", "chain", "red_flags"],
    }
    items = s.score_document(doc, {"owner_name": "X", "survey_number": "9"})
    names = {i.field: i.outcome for i in items}
    assert "owner_name" not in names and "chain" not in names
    assert names["survey_number"] == SPURIOUS
    assert names["area"] == CORRECT
