import io
import os
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# 2026-08-21: a manual-report PDF whose excerpt was Devanagari (Hindi/Marathi)
# text rendered as solid black boxes — confirmed by generating a real PDF and
# rasterizing it, not just inspected in code. Root cause: ReportLab's default
# "Helvetica" is one of Adobe's base-14 fonts, which only covers Latin-1 — any
# codepoint it has no glyph for falls back to a filled .notdef box, which is
# exactly what looked like "the text is being redacted". Fix: bundle a
# Unicode font with Devanagari coverage (Noto Sans Devanagari, SIL Open Font
# License — free to redistribute, see assets/fonts/NotoSansDevanagari-OFL.txt)
# and use it for any style that renders excerpt/citation/note/case-metadata
# text, since that's reviewer- or document-supplied and could be any script.
# Scope deliberately limited to Devanagari for now (user's call, 2026-08-21)
# — Tamil/Telugu/Kannada (also mentioned in the extraction prompt) would need
# their own font files plus per-character script-run detection to mix
# correctly within one paragraph, which is real added scope, not a one-line
# follow-up. Also note: ReportLab does not perform OpenType shaping (no
# GSUB/GPOS, unlike a browser or a proper text-shaping engine such as
# HarfBuzz), so complex Devanagari conjuncts/matra reordering won't always be
# typographically perfect even with the right font — this fix resolves the
# "renders as a black box" bug, not full Indic shaping correctness.
_FONT_NAME = "NotoSansDevanagari"
_FONT_PATH = os.path.join(os.path.dirname(__file__), "..", "assets", "fonts", "NotoSansDevanagari.ttf")

try:
    pdfmetrics.registerFont(TTFont(_FONT_NAME, _FONT_PATH))
except Exception:
    # Fails open to Helvetica (the pre-fix behavior) rather than blocking PDF
    # export entirely if the font asset is somehow missing/unreadable — a
    # Devanagari excerpt would go back to rendering as a black box, but every
    # other excerpt still exports.
    _FONT_NAME = "Helvetica"


def _escape(text: str) -> str:
    """ReportLab's Paragraph interprets a minimal XML/HTML-like markup — escape
    user-supplied excerpt/note text so a stray '<', '>', or '&' typed by a lawyer
    (or transcribed off a document) can't be misread as markup and break the PDF."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_excerpt_report_pdf(case: Dict[str, Any], excerpts: List[Dict[str, Any]]) -> bytes:
    """Renders the manual report builder's ordered excerpts into a PDF.

    Reuses the same ReportLab story-builder pattern as report_service.py's
    fixed-summary PDF (SimpleDocTemplate + a growing `story` list of flowables),
    but is a standalone function rather than an addition to ReportGenerationService
    — that class's constructor and layout are tied to a fixed 4-row case-metadata
    table, not an ordered list of citations, so extending it would mean reshaping
    it around a second, unrelated use case.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40,
    )
    story = []

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=20,
        textColor=colors.HexColor("#1E3A8A"),
        spaceAfter=10,
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#991B1B"),
    )
    citation_style = ParagraphStyle(
        "Citation",
        parent=styles["Normal"],
        # Document filenames are effectively always Latin/ASCII in practice,
        # but this line can still carry reviewer/document-supplied text, so
        # it gets the Unicode font too rather than assuming — losing the
        # "-Bold" weight (Noto Sans Devanagari is only registered at Regular,
        # see module-level comment above) is a small cosmetic tradeoff for
        # not risking a black box here.
        fontName=_FONT_NAME,
        fontSize=9,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=4,
    )
    excerpt_style = ParagraphStyle(
        "Excerpt",
        parent=styles["Normal"],
        fontName=_FONT_NAME,  # the actual document text — the whole reason this fix exists
        fontSize=11,
        leading=15,
        leftIndent=12,
        spaceAfter=6,
    )
    translation_style = ParagraphStyle(
        "Translation",
        parent=styles["Italic"],
        fontName=_FONT_NAME,  # translated output can still contain proper nouns in the original script
        fontSize=10,
        leading=14,
        leftIndent=12,
        textColor=colors.HexColor("#374151"),
        spaceAfter=6,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Italic"],
        fontName=_FONT_NAME,  # reviewer-typed note, could be any script
        fontSize=9,
        textColor=colors.HexColor("#6B7280"),
        spaceAfter=14,
    )

    story.append(Paragraph("PROPERTY DUE DILIGENCE REPORT", title_style))
    story.append(Paragraph(
        "DRAFT — assembled from reviewer-selected document excerpts. Requires lawyer review before use.",
        disclaimer_style,
    ))
    story.append(Spacer(1, 12))

    meta_data = [
        ["Case Identifier:", _escape(str(case.get("id", "N/A")))],
        ["Property:", _escape(case.get("property_name") or "N/A")],
        ["Location:", _escape(case.get("location") or "N/A")],
        ["Survey Number:", _escape(case.get("survey_number") or "N/A")],
    ]
    meta_table = Table(meta_data, colWidths=[130, 370])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1F2937")),
        # property_name/location are reviewer-entered case fields, not
        # guaranteed to be Latin script, same reasoning as the excerpt styles
        # above.
        ("FONTNAME", (0, 0), (-1, -1), _FONT_NAME),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph(f"Excerpts ({len(excerpts)})", styles["Heading2"]))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#E5E7EB"), spaceAfter=10))

    if not excerpts:
        story.append(Paragraph("No excerpts have been added to this report yet.", styles["Normal"]))
    else:
        for index, excerpt in enumerate(excerpts, start=1):
            document_label = _escape(excerpt.get("document_name") or str(excerpt.get("document_id", "")))
            story.append(Paragraph(
                f"{index}. {document_label} &mdash; Page {excerpt.get('page_number')}",
                citation_style,
            ))
            story.append(Paragraph(_escape(excerpt.get("excerpt_text", "")), excerpt_style))
            # english_text is populated by ReportBuilderService.export_pdf()
            # (translates every excerpt fresh at export time — excerpts carry
            # no language tag, so there's no cheaper source of truth) —
            # absent entirely for any caller that builds a PDF without going
            # through that translation step (e.g. tests), in which case this
            # line is simply skipped rather than showing an empty "English:".
            if excerpt.get("english_text"):
                story.append(Paragraph(f"English: {_escape(excerpt['english_text'])}", translation_style))
            if excerpt.get("note"):
                story.append(Paragraph(f"Note: {_escape(excerpt['note'])}", note_style))

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
