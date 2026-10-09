"""Per-field comparison rules (docs/EXTRACTION_QUALITY.md section 1.4).

Every scored value gets exactly one outcome:
  correct   exact match after normalisation, or an `alternates` match
  close     names / free text / identifiers / area: similar but not identical
  wrong     a value was returned and it is not the right one
  missing   a value was expected, null returned
  spurious  null was expected, a value returned
A field that is unlabelled is not scored at all (no Item is produced).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .normalize import (
    ID_PREFIX_WORDS, ascii_digits, has_non_latin_letters, is_null, name_tokens,
    norm_text, ratio, tokens,
)

CORRECT, CLOSE, WRONG, MISSING, SPURIOUS = "correct", "close", "wrong", "missing", "spurious"
OUTCOMES = (CORRECT, CLOSE, WRONG, MISSING, SPURIOUS)

NAME_CLOSE_THRESHOLD = 0.85
FREETEXT_CLOSE_F1 = 0.80
AREA_TOLERANCE = 0.005
RED_FLAG_OVERLAP = 0.60

FIELD_KINDS: Dict[str, str] = {
    "document_type": "enum",
    "owner_name": "name",
    "previous_owner_name": "name",
    "survey_number": "identifier",
    "transaction_date": "date",
    "transaction_type": "enum",
    "property_location": "freetext",
    "property_boundaries": "freetext",
    "area": "area",
    "registration_number": "identifier",
    "language_detected": "language",
}
SCALAR_FIELDS = tuple(FIELD_KINDS)
LIST_FIELDS = ("chain", "red_flags")
# Top-level fields that count in the headline numbers. The chain.* items
# below are detail rows and are deliberately not in this list (no double
# counting).
SCORED_FIELDS = SCALAR_FIELDS + LIST_FIELDS
CRITICAL_FIELDS = (
    "owner_name", "previous_owner_name", "survey_number",
    "transaction_date", "registration_number", "area",
)

_LANGUAGE_ALIASES = {
    "mr": "marathi", "hi": "hindi", "en": "english", "ta": "tamil",
    "te": "telugu", "kn": "kannada", "gu": "gujarati", "bn": "bengali",
}


@dataclass
class Item:
    field: str
    outcome: str
    expected: Any = None
    predicted: Any = None
    form: str = "script"           # "script" | "translit" (names only)
    note: Optional[str] = None     # e.g. "day_month_swap"


# ---------------------------------------------------------------- comparers
# Each returns (outcome, note) for a non-null expected and non-null predicted.

def _cmp_enum(pred: str, exps: Sequence[str]) -> Tuple[str, Optional[str]]:
    def k(s): return norm_text(s).replace(" ", "_")
    return (CORRECT, None) if any(k(pred) == k(e) for e in exps) else (WRONG, None)


def _cmp_language(pred: str, exps: Sequence[str]) -> Tuple[str, Optional[str]]:
    def k(s):
        n = norm_text(s)
        return _LANGUAGE_ALIASES.get(n, n)
    return (CORRECT, None) if any(k(pred) == k(e) for e in exps) else (WRONG, None)


def _token_cover(small: List[str], large: List[str]) -> float:
    """Mean over `small` of the best similarity to any token of `large`; a
    single-letter token is an initial and matches any token starting with it."""
    if not small or not large:
        return 0.0
    total = 0.0
    for t in small:
        best = 0.0
        for u in large:
            if len(t) == 1 and u.startswith(t) or len(u) == 1 and t.startswith(u):
                s = 1.0
            else:
                s = ratio(t, u)
            best = max(best, s)
        total += best
    return total / len(small)


def _cmp_name(pred: str, exps: Sequence[str]) -> Tuple[str, Optional[str]]:
    p = name_tokens(pred)
    best = WRONG
    for e in exps:
        et = name_tokens(e)
        if p and sorted(p) == sorted(et):
            return CORRECT, None
        small, large = (p, et) if len(p) <= len(et) else (et, p)
        # A one-word name vs a longer name is not "close" (a bare surname
        # matching a full name is exactly the mistake that matters).
        if len(small) < 2 and len(large) > 1:
            continue
        if _token_cover(small, large) >= NAME_CLOSE_THRESHOLD:
            best = CLOSE
    return best, None


def _id_exact_key(s: str) -> str:
    return re.sub(r"\s+", "", ascii_digits(str(s)).casefold())


def _id_close_key(s: str) -> str:
    n = ascii_digits(str(s)).casefold()
    n = re.sub(r"[^\w/\-ऀ-ॿ\s]", " ", n)
    kept = [t for t in re.split(r"\s+", n) if t and t.strip(".") not in ID_PREFIX_WORDS]
    return "".join(kept)


def _cmp_identifier(pred: str, exps: Sequence[str]) -> Tuple[str, Optional[str]]:
    if any(_id_exact_key(pred) == _id_exact_key(e) for e in exps):
        return CORRECT, None
    pc = _id_close_key(pred)
    if pc and any(pc == _id_close_key(e) for e in exps):
        return CLOSE, None
    return WRONG, None


_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def _cmp_date(pred: str, exps: Sequence[str]) -> Tuple[str, Optional[str]]:
    p = ascii_digits(str(pred)).strip()
    if any(p == ascii_digits(str(e)).strip() for e in exps):
        return CORRECT, None
    pm = _ISO.match(p)
    if pm:
        for e in exps:
            em = _ISO.match(ascii_digits(str(e)).strip())
            if em and pm.group(1) == em.group(1) and pm.group(2) == em.group(3) \
                    and pm.group(3) == em.group(2) and pm.group(2) != pm.group(3):
                return WRONG, "day_month_swap"
    return WRONG, None


_UNIT_SUBS: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"sq\.?\s*(?:ft|feet|foot)\.?|square\s+(?:feet|foot)|sqft", re.I), " sqft "),
    (re.compile(r"sq\.?\s*(?:m|mtr|mtrs|meter|meters|metre|metres)\.?|square\s+(?:meters?|metres?)|sqm|चौ\.?\s*मी\.?", re.I), " sqm "),
    (re.compile(r"hectares?|हेक्टर|हेक्टेयर|\bha\b", re.I), " hectare "),
    (re.compile(r"acres?|\bac\b|एकर", re.I), " acre "),
    (re.compile(r"gunth?as?|gunt[ae]s?|गुंठा|गुंठे", re.I), " guntha "),
    (re.compile(r"\bares?\b|\bआर\b", re.I), " are "),
]
_AREA_PAIR = re.compile(r"(\d+(?:\.\d+)?)\s*([A-Za-zऀ-ॿ]+)")


def parse_area(text: str) -> List[Tuple[str, float]]:
    s = ascii_digits(str(text))
    for pat, repl in _UNIT_SUBS:
        s = pat.sub(repl, s)
    pairs = [(unit.casefold(), float(num)) for num, unit in _AREA_PAIR.findall(s)]
    return sorted(pairs)


def _cmp_area(pred: str, exps: Sequence[str]) -> Tuple[str, Optional[str]]:
    pp = parse_area(pred)
    best = WRONG
    for e in exps:
        ep = parse_area(e)
        if pp and ep:
            if pp == ep:
                return CORRECT, None
            if len(pp) == len(ep) and all(
                pu == eu and abs(pv - ev) <= AREA_TOLERANCE * max(abs(ev), 1e-9)
                for (pu, pv), (eu, ev) in zip(pp, ep)
            ):
                best = CLOSE
        elif norm_text(pred) == norm_text(e):
            return CORRECT, None
    return best, None


def token_f1(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    common = 0
    pool = list(tb)
    for t in ta:
        if t in pool:
            pool.remove(t)
            common += 1
    if common == 0:
        return 0.0
    p, r = common / len(ta), common / len(tb)
    return 2 * p * r / (p + r)


def _cmp_freetext(pred: str, exps: Sequence[str]) -> Tuple[str, Optional[str]]:
    best = WRONG
    for e in exps:
        if norm_text(pred) == norm_text(e):
            return CORRECT, None
        if token_f1(pred, e) >= FREETEXT_CLOSE_F1:
            best = CLOSE
    return best, None


_COMPARERS: Dict[str, Callable[[str, Sequence[str]], Tuple[str, Optional[str]]]] = {
    "enum": _cmp_enum, "language": _cmp_language, "name": _cmp_name,
    "identifier": _cmp_identifier, "date": _cmp_date, "area": _cmp_area,
    "freetext": _cmp_freetext,
}


def score_scalar(
    name: str, expected: Any, alternates: Sequence[str], predicted: Any,
    transliteration: Optional[str] = None,
) -> Item:
    kind = FIELD_KINDS[name]
    if is_null(expected):
        return Item(name, CORRECT if is_null(predicted) else SPURIOUS, expected, predicted)
    if is_null(predicted):
        return Item(name, MISSING, expected, predicted)

    exps = [str(expected)] + [str(a) for a in alternates]
    form = "script"
    # Names only: a Latin-letter prediction is compared with the labelled
    # transliteration when there is one, and reported as its own form, so a
    # romanisation difference is never counted as an extraction error.
    if kind == "name" and transliteration and not has_non_latin_letters(str(predicted)):
        exps, form = [str(transliteration)], "translit"
    outcome, note = _COMPARERS[kind](str(predicted), exps)
    return Item(name, outcome, expected, predicted, form=form, note=note)


# -------------------------------------------------------------------- chain

def _ordered(chain: Any) -> List[Dict[str, Any]]:
    links = [l for l in (chain or []) if isinstance(l, dict)]
    return sorted(links, key=lambda l: (l.get("order") is None, l.get("order") or 0))


def score_chain(expected: List[Dict[str, Any]], predicted: Any) -> List[Item]:
    exp, pred = _ordered(expected), _ordered(predicted)
    items: List[Item] = []
    sub: List[Item] = []
    sub.append(Item("chain.link_count", CORRECT if len(exp) == len(pred) else WRONG, len(exp), len(pred)))
    all_exact = len(exp) == len(pred)
    all_lenient = len(exp) == len(pred)
    for i, e in enumerate(exp):
        p = pred[i] if i < len(pred) else None
        for key, kind in (("owner", "name"), ("date", "date"), ("type", "enum")):
            ev = e.get(key)
            if ev is None:
                continue  # that part of this link was not labelled
            if p is None:
                it = Item(f"chain.{key}", MISSING, ev, None)
            elif kind == "name":
                it = score_scalar("owner_name", ev, [], p.get(key))
                it.field = f"chain.{key}"
            elif kind == "date":
                it = score_scalar("transaction_date", ev, [], p.get(key))
                it.field = f"chain.{key}"
            else:
                it = score_scalar("document_type", ev, [], p.get(key))
                it.field = f"chain.{key}"
            sub.append(it)
            if it.outcome != CORRECT:
                all_exact = False
            if it.outcome not in (CORRECT, CLOSE):
                all_lenient = False
    if not exp and not pred:
        agg = CORRECT
    elif not exp:
        agg = SPURIOUS
    elif not pred:
        agg = MISSING
    elif all_exact:
        agg = CORRECT
    elif all_lenient:
        agg = CLOSE
    else:
        agg = WRONG
    items.append(Item("chain", agg, expected, predicted))
    items.extend(sub)
    return items


# --------------------------------------------------------------- red flags

def _flag_matches(e: Dict[str, Any], p: Dict[str, Any]) -> bool:
    if norm_text(e.get("type") or "other") != norm_text(p.get("type") or "other"):
        return False
    es = e.get("source_text")
    if is_null(es):
        return True
    ps = p.get("source_text")
    return not is_null(ps) and token_f1(str(es), str(ps)) >= RED_FLAG_OVERLAP


def score_red_flags(expected: List[Dict[str, Any]], predicted: Any) -> List[Item]:
    exp = [f for f in (expected or []) if isinstance(f, dict)]
    pred = [f for f in (predicted or []) if isinstance(f, dict)]
    unmatched = list(pred)
    items: List[Item] = []
    for e in exp:
        hit = next((p for p in unmatched if _flag_matches(e, p)), None)
        if hit is not None:
            unmatched.remove(hit)
            items.append(Item("red_flags", CORRECT, e, hit))
        else:
            items.append(Item("red_flags", MISSING, e, None))
    for p in unmatched:
        items.append(Item("red_flags", SPURIOUS, None, p))
    return items


# ---------------------------------------------------------------- document

def score_document(expected_doc: Dict[str, Any], predicted: Dict[str, Any]) -> List[Item]:
    """Scores one extraction against one expected.json. `expected_doc` must
    already be validated (see loader.validate_expected)."""
    fields = expected_doc.get("fields", {})
    alternates = expected_doc.get("alternates", {})
    translits = expected_doc.get("transliterations", {})
    unlabelled = set(expected_doc.get("unlabelled", []))
    predicted = predicted or {}
    items: List[Item] = []

    for name in SCALAR_FIELDS:
        if name in unlabelled or name not in fields:
            continue
        items.append(score_scalar(
            name, fields[name], alternates.get(name, []), predicted.get(name),
            translits.get(name),
        ))
    if "chain" not in unlabelled and "chain" in expected_doc:
        items.extend(score_chain(expected_doc["chain"], predicted.get("chain")))
    if "red_flags" not in unlabelled and "red_flags" in expected_doc:
        items.extend(score_red_flags(expected_doc["red_flags"], predicted.get("red_flags")))
    return items
