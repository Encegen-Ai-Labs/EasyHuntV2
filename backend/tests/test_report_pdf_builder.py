import fitz

from app.services.report_pdf_builder import build_excerpt_report_pdf

CASE = {"id": "case-1", "property_name": "Meridian Plot 42", "location": "Pune", "survey_number": "SY-1"}


def test_builds_a_real_pdf_with_no_excerpts():
    pdf_bytes = build_excerpt_report_pdf(CASE, [])

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 0


def test_builds_a_real_pdf_with_excerpts():
    excerpts = [
        {
            "document_id": "doc-1",
            "document_name": "sale_deed.pdf",
            "page_number": 3,
            "excerpt_text": "The property described herein is transferred in full.",
            "note": "Key ownership clause",
        },
        {
            "document_id": "doc-2",
            "document_name": None,  # falls back to document_id
            "page_number": 1,
            "excerpt_text": "Survey number 45 confirmed.",
            "note": None,
        },
    ]

    pdf_bytes = build_excerpt_report_pdf(CASE, excerpts)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 500  # sanity: real content was rendered, not an empty shell


def test_does_not_crash_on_excerpt_text_containing_markup_like_characters():
    # ReportLab's Paragraph interprets a minimal XML-like markup — text containing
    # literal '<', '>', '&' (plausible in a legal document transcription, e.g.
    # "A & B Properties" or a stray '<') must be escaped, not passed through raw,
    # or doc.build() would raise instead of silently mis-rendering.
    excerpts = [{
        "document_id": "doc-1",
        "document_name": "A & B Properties <Deed>",
        "page_number": 1,
        "excerpt_text": "Owner: A & B Properties. Clause <5> applies.",
        "note": "Check < and & handling",
    }]

    pdf_bytes = build_excerpt_report_pdf(CASE, excerpts)

    assert pdf_bytes.startswith(b"%PDF")


def test_handles_missing_case_metadata_gracefully():
    pdf_bytes = build_excerpt_report_pdf({"id": "case-1"}, [])

    assert pdf_bytes.startswith(b"%PDF")


def test_devanagari_excerpt_uses_the_bundled_unicode_font():
    # Regression test for the "exported/selected text is being redacted" bug
    # (2026-08-21) — confirmed live by rendering a real PDF to an image: a
    # Devanagari (Marathi/Hindi) excerpt rendered as solid black boxes,
    # because ReportLab's default "Helvetica" has no Devanagari glyphs and
    # falls back to a filled .notdef glyph for every character. Checks the
    # PDF actually references the bundled font rather than asserting on
    # rendered pixels (slow/fragile) — see report_pdf_builder.py's
    # module-level comment for the full story.
    excerpts = [{
        "document_id": "doc-1",
        "document_name": "sale_deed.pdf",
        "page_number": 1,
        "excerpt_text": "दिनांक विषयी वाक्य",
        "note": "सत्यापित",
    }]

    pdf_bytes = build_excerpt_report_pdf(CASE, excerpts)

    assert pdf_bytes.startswith(b"%PDF")
    assert b"NotoSansDevanagari" in pdf_bytes


def test_devanagari_excerpt_text_survives_into_the_real_rendered_pdf():
    # Stronger than the font-name check above: actually renders the PDF and
    # extracts its text, confirming every Devanagari codepoint from the
    # excerpt is really there — the pre-fix Helvetica fallback extracted as a
    # run of unrelated Latin-range characters instead of the real text.
    excerpts = [{
        "document_id": "doc-1",
        "document_name": "sale_deed.pdf",
        "page_number": 1,
        "excerpt_text": "दिनांक विषयी वाक्य",
        "note": None,
    }]

    pdf_bytes = build_excerpt_report_pdf(CASE, excerpts)

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    extracted = doc[0].get_text()
    doc.close()

    for ch in set("दिनांकविषयीवाक्य"):
        assert ch in extracted
