import io
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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


def build_draft_pdf(draft) -> bytes:
    """Writes an edited report draft (schemas.report_generation.ReportDraft,
    title-search kind) as a PDF. Every text style uses the Unicode font so
    Devanagari in an extract does not turn into black boxes (see the module
    comment at the top)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("DraftTitle", parent=styles["Heading1"], fontName=_FONT_NAME, fontSize=18, alignment=1, spaceAfter=14)
    heading_style = ParagraphStyle("DraftHeading", parent=styles["Heading2"], fontName=_FONT_NAME, fontSize=13, spaceBefore=12, spaceAfter=6)
    body_style = ParagraphStyle("DraftBody", parent=styles["Normal"], fontName=_FONT_NAME, fontSize=10.5, leading=15, spaceAfter=6)
    cell_style = ParagraphStyle("DraftCell", parent=styles["Normal"], fontName=_FONT_NAME, fontSize=9, leading=12)

    def paragraph(text: str, style) -> Paragraph:
        return Paragraph(_escape(text).replace("\n", "<br/>"), style)

    story = [paragraph(draft.title.upper(), title_style)]
    for section in draft.sections:
        story.append(paragraph(section.heading, heading_style))
        for block in section.blocks:
            if block.type == "table" and block.columns:
                width = len(block.columns)
                rows = [[paragraph(c, cell_style) for c in block.columns]]
                rows += [
                    [paragraph(row[i] if i < len(row) else "", cell_style) for i in range(width)]
                    for row in block.rows
                ]
                table = Table(rows, colWidths=[500 / width] * width, repeatRows=1)
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#9CA3AF")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                story.append(table)
                story.append(Spacer(1, 8))
            elif (block.text or "").strip():
                story.append(paragraph(block.text, body_style))
    doc.build(story)
    return buffer.getvalue()
