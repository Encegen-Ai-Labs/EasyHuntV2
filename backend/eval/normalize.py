"""Text normalisation shared by the field scorers.

Standard library only (difflib, not rapidfuzz) so the harness runs in the
existing venv without new dependencies.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from typing import List

# Words that precede a person's name and are not part of it. Compared after
# norm_text(), so punctuation and case are already gone ("Shri." -> "shri").
HONORIFICS = {
    "shri", "shree", "sri", "shrimati", "smt", "sau", "mr", "mrs", "ms", "miss",
    "late", "kai", "dr",
    "श्री", "श्रीमती", "श्रीमान", "सौ", "कै", "स्व", "कु", "कुमारी",
}

# Words that precede a survey / plot / registration identifier and are not
# part of it ("Gat No. 45/2B" -> "45/2b"). Only used for the *close* match;
# the exact match keeps them.
ID_PREFIX_WORDS = {
    "gat", "survey", "sur", "s", "sy", "plot", "khasra", "cts", "fp", "no", "nos",
    "number", "reg", "registration",
    "नं", "क्र", "क्रमांक", "गट", "सर्वे", "सर्व्हे", "नंबर", "क्रं",
}


def ascii_digits(text: str) -> str:
    """Maps digits of any script (Devanagari, Tamil, Telugu, Kannada...) to
    ASCII 0-9, leaving every other character alone."""
    out = []
    for ch in text:
        d = unicodedata.decimal(ch, None)
        out.append(str(d) if d is not None else ch)
    return "".join(out)


def norm_text(text: str) -> str:
    """NFC, ASCII digits, casefold, every non letter/mark/digit character
    replaced by a space, whitespace collapsed. Combining marks are kept:
    Devanagari vowel signs are marks, and dropping them changes the word."""
    text = ascii_digits(unicodedata.normalize("NFC", str(text))).casefold()
    chars = []
    for ch in text:
        cat = unicodedata.category(ch)
        chars.append(ch if cat[0] in ("L", "M", "N") else " ")
    return re.sub(r"\s+", " ", "".join(chars)).strip()


def tokens(text: str) -> List[str]:
    n = norm_text(text)
    return n.split(" ") if n else []


def name_tokens(text: str) -> List[str]:
    return [t for t in tokens(text) if t not in HONORIFICS]


def ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def is_null(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def has_non_latin_letters(text: str) -> bool:
    return any(ch.isalpha() and ord(ch) > 0x24F for ch in str(text))
