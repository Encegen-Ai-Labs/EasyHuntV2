"""Cleans transcribed page text before it is stored or shown.

Gemini (and sometimes OCR) leaves two kinds of markup in a transcription that
a lawyer should never see: `<br>` tags and stray `|` characters. Both come from
the way tables are written. The one legitimate use of `|` is a real table
(GitHub-style markdown: a header row, a `---` separator row, body rows), which
the screens render as an actual table. Everything else is removed:

- `<br>` outside a table becomes a line break; inside a table row it becomes a
  space, because a newline would split the row.
- A `|` outside a table (an OCR misread of a danda or a ruled line, or a model
  habit) becomes a space.

Idempotent: cleaning already-clean text returns it unchanged.
"""

import re

_BR_RE = re.compile(r"<\s*/?\s*br\s*/?\s*>", re.IGNORECASE)
_NBSP_RE = re.compile(r"&nbsp;| ", re.IGNORECASE)
_SEPARATOR_ROW_RE = re.compile(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$")
_PIPE_RE = re.compile(r"[ \t]*\|[ \t]*")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MANY_BLANK_LINES_RE = re.compile(r"\n[ \t]*\n[ \t]*\n+")


def _is_table_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.count("|") >= 2 or (stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 1)


def _is_table_block(lines: list[str]) -> bool:
    """A run of pipe lines is a table when it has at least two rows and either
    a separator row or consistent pipe counts (a table that omitted the
    separator is still a table; two unrelated lines with stray pipes are not)."""
    if len(lines) < 2:
        return False
    if any(_SEPARATOR_ROW_RE.match(line) and "-" in line for line in lines):
        return True
    counts = {line.strip().count("|") for line in lines}
    return len(counts) == 1 and min(counts) >= 2


def _clean_table_row(line: str) -> str:
    row = _BR_RE.sub(" ", line)
    row = _NBSP_RE.sub(" ", row)
    return _MULTI_SPACE_RE.sub(" ", row).rstrip()


def _clean_prose_line(line: str) -> str:
    line = _NBSP_RE.sub(" ", line)
    line = _PIPE_RE.sub(" ", line)
    return _MULTI_SPACE_RE.sub(" ", line).rstrip()


def clean_page_text(text: str | None) -> str | None:
    """Removes `<br>` tags and non-table `|` characters from transcribed text,
    keeping real tables intact. None and empty strings pass through."""
    if not text:
        return text

    text = _BR_RE.sub("\n", text)
    # A <br> inside a table row was just turned into a newline, which splits
    # the row. Join a row's continuation back onto it: a table line that does
    # not start with a pipe but follows a table line that did not end with one.
    lines = text.split("\n")
    merged: list[str] = []
    for line in lines:
        if merged and _is_open_table_row(merged[-1]) and not _looks_like_new_row(line):
            merged[-1] = merged[-1] + " " + line.strip()
        else:
            merged.append(line)

    output: list[str] = []
    index = 0
    while index < len(merged):
        if not _is_table_line(merged[index]):
            output.append(_clean_prose_line(merged[index]))
            index += 1
            continue

        end = index
        while end < len(merged) and _is_table_line(merged[end]):
            end += 1
        block = merged[index:end]
        if _is_table_block(block):
            output.extend(_clean_table_row(line) for line in block)
        else:
            output.extend(_clean_prose_line(line) for line in block)
        index = end

    return _MANY_BLANK_LINES_RE.sub("\n\n", "\n".join(output))


def _is_open_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and not stripped.endswith("|")


def _looks_like_new_row(line: str) -> bool:
    return line.strip().startswith("|")


def split_blocks(text: str | None) -> list[dict]:
    """Splits cleaned text into paragraph and table blocks, for the report
    editor and the Word/PDF writers: [{"type": "text", "text": ...} |
    {"type": "table", "columns": [...], "rows": [[...], ...]}]. Only runs that
    clean_page_text() recognises as tables become table blocks."""
    cleaned = clean_page_text(text) or ""
    lines = cleaned.split("\n")
    blocks: list[dict] = []
    prose: list[str] = []

    def flush_prose() -> None:
        joined = "\n".join(prose).strip("\n")
        if joined.strip():
            blocks.append({"type": "text", "text": joined})
        prose.clear()

    index = 0
    while index < len(lines):
        if not _is_table_line(lines[index]):
            prose.append(lines[index])
            index += 1
            continue
        end = index
        while end < len(lines) and _is_table_line(lines[end]):
            end += 1
        run = lines[index:end]
        if _is_table_block(run):
            flush_prose()
            rows = [
                [cell.strip() for cell in line.strip().strip("|").split("|")]
                for line in run
                if not _SEPARATOR_ROW_RE.match(line)
            ]
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            blocks.append({"type": "table", "columns": rows[0], "rows": rows[1:]})
        else:
            prose.extend(run)
        index = end
    flush_prose()
    return blocks
