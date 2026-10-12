"""Run inside the built image to prove the one thing unit tests cannot: that a
bank-format report with Marathi text really becomes a PDF (LibreOffice, fonts).

    docker run --rm <image> python -m scripts.smoke_render
"""
import sys

import pymupdf

from app.schemas.report_generation import DraftField, ReportDraft
from app.services import report_formats
from app.services.report_generation_service import render_pdf

MARATHI = "अनंत गणपत पाशिलकर"


def main() -> int:
    bank = next(f["id"] for f in report_formats.list_formats() if f["kind"] == "bank")
    manifest = report_formats.get_manifest(bank)
    fields = [
        DraftField(name=f["name"], label=f.get("description", ""), type=f.get("type", "text"),
                   value=MARATHI if f["name"] in ("mortgagor_name", "borrower_name") else "")
        for f in manifest["fields"]
    ]
    pdf = render_pdf(ReportDraft(format_id=bank, kind="bank", title="smoke", fields=fields, loops=[]))
    if not pdf.startswith(b"%PDF"):
        print("FAIL: not a PDF")
        return 1
    text = "".join(page.get_text() for page in pymupdf.open(stream=pdf, filetype="pdf"))
    missing = [ch for ch in set(MARATHI.replace(" ", "")) if ch not in text]
    if missing:
        print(f"FAIL: Marathi characters missing from the PDF text: {missing}")
        return 1
    print(f"ok: {bank} -> PDF, {len(pdf)} bytes, Marathi text present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
