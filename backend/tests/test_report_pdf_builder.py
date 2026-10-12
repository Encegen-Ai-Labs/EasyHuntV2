"""The title-search PDF writer: real PDF bytes, and Devanagari text that really arrives."""
import fitz

from app.schemas.report_generation import DraftBlock, DraftSection, ReportDraft
from app.services.report_pdf_builder import build_draft_pdf


def _draft(*blocks):
    return ReportDraft(
        format_id="title-search", kind="title_search", title="Title Search Report",
        sections=[DraftSection(id="s", heading="Extracts", blocks=list(blocks))],
    )


def test_an_empty_draft_still_makes_a_pdf():
    assert build_draft_pdf(_draft()).startswith(b"%PDF")


def test_text_with_markup_characters_does_not_break_the_pdf():
    pdf = build_draft_pdf(_draft(DraftBlock(type="paragraph", text="A < B & C > D")))
    assert pdf.startswith(b"%PDF")


def test_devanagari_text_uses_the_bundled_unicode_font():
    # Regression (2026-08-21): without a Devanagari font every character rendered
    # as a solid black box (ReportLab's Helvetica has no such glyphs).
    pdf = build_draft_pdf(_draft(DraftBlock(type="paragraph", text="दिनांक विषयी वाक्य")))
    assert b"NotoSansDevanagari" in pdf


def test_devanagari_text_survives_into_the_rendered_pdf():
    pdf = build_draft_pdf(_draft(
        DraftBlock(type="paragraph", text="दिनांक विषयी वाक्य"),
        DraftBlock(type="table", columns=["नाव"], rows=[["सत्यापित"]]),
    ))
    doc = fitz.open(stream=pdf, filetype="pdf")
    extracted = "".join(page.get_text() for page in doc)
    doc.close()
    for ch in set("दिनांकविषयीवाक्यनावसत्यापित"):
        assert ch in extracted
