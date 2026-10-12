"""Builds an editable report draft from a case's approved documents, and writes
a draft (as the lawyer edited it) out as Word or PDF.

A draft is plain JSON the browser edits:
- title search: ordered sections of paragraphs and tables;
- bank format: the bank template's fields and repeating tables, taken from its
  .fields.json manifest, pre-filled where the documents say something.

Nothing that needs legal judgement is filled in. A manifest field marked
must_confirm (opinion, marketability, adverse remarks, tenure, ...) is always
left empty for the lawyer to write, and the title search's opinion section
holds a visible placeholder.
"""
import io
import shutil
import subprocess
import tempfile
from collections import OrderedDict
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.exceptions import PropertySystemException
from app.core.logging import logger
from app.repositories.base import BaseRepository
from app.repositories.doc_repo import APPROVED_STATUSES, DocumentRepository
from app.repositories.flag_repo import FlagRepository
from app.schemas.report_generation import DraftBlock, DraftField, DraftLoop, DraftSection, ReportDraft
from app.services import report_autofill, report_formats
from app.services.doc_service import DocumentService
from app.services.report_builder_service import ReportBuilderService
from app.services.text_cleanup import split_blocks

OPINION_PLACEHOLDER = "[Advocate's opinion to be entered here.]"
PDF_CONVERTER_NAMES = ("soffice", "libreoffice")
PDF_CONVERSION_TIMEOUT_SECONDS = 90

# Group order and heading for a bank form's fields, by manifest "source".
FIELD_GROUPS = OrderedDict([
    ("case_intake", "Case and loan details"),
    ("profile", "Advocate details"),
    ("search_office", "Search office details"),
    ("extracted", "From the documents"),
    ("drafted", "Opinion and checklist"),
])


def _today_text() -> str:
    return date.today().strftime("%d/%m/%Y")


def _titlecase(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


class ReportGenerationService:
    def __init__(
        self,
        doc_service: DocumentService,
        doc_repo: DocumentRepository,
        generic_repo: BaseRepository,
        flag_repo: FlagRepository,
        report_builder: ReportBuilderService,
    ):
        self.doc_service = doc_service
        self.doc_repo = doc_repo
        self.generic_repo = generic_repo
        self.flag_repo = flag_repo
        self.report_builder = report_builder
        # Replaceable so tests need no network.
        self._autofill = report_autofill.autofill

    # ---- drafts -------------------------------------------------------

    def build_draft(self, case_id: str, format_id: str, current_user: Dict[str, Any]) -> ReportDraft:
        case = self.doc_service.authorize_case_access(case_id, current_user)
        context = self._load_context(case, current_user)
        if not context["documents"]:
            raise PropertySystemException(
                "Approve at least one document before creating a report.", status_code=409
            )
        if report_formats.is_title_search(format_id):
            return self._title_search_draft(context)
        return self._bank_draft(format_id, context)

    def _load_context(self, case: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        documents = [d for d in self.doc_repo.list_by_case(case["id"]) if d.get("status") in APPROVED_STATUSES]
        fields_by_doc: Dict[str, Dict[str, Any]] = {}
        for document in documents:
            extraction = self.generic_repo.select_one(
                "extractions", {"document_id": document["id"]}, order_by="id"
            )
            validated = (extraction or {}).get("validated_json_output")
            fields_by_doc[document["id"]] = validated if isinstance(validated, dict) else {}

        chain: List[Dict[str, Any]] = []
        seen = set()
        for document in documents:
            for link in fields_by_doc[document["id"]].get("chain") or []:
                if not isinstance(link, dict):
                    continue
                key = (_text(link.get("owner")), _text(link.get("date")), _text(link.get("type")), _text(link.get("survey")))
                if key in seen or not key[0]:
                    continue
                seen.add(key)
                chain.append({**link, "source": document.get("file_name") or ""})
        chain.sort(key=lambda link: _text(link.get("date")) or "9999-99-99")

        try:
            flags = self.flag_repo.list_by_case(case["id"])
        except Exception:
            logger.exception("report.flags_unavailable | case_id=%s", case["id"])
            flags = []

        excerpts = self.report_builder.get_report_with_excerpts(case["id"], current_user)["excerpts"]
        return {
            "case": case,
            "documents": documents,
            "fields_by_doc": fields_by_doc,
            "chain": chain,
            "flags": flags,
            "excerpts": excerpts,
        }

    @staticmethod
    def _distinct(context: Dict[str, Any], key: str) -> List[str]:
        values: List[str] = []
        for document in context["documents"]:
            value = _text(context["fields_by_doc"][document["id"]].get(key))
            if value and value not in values:
                values.append(value)
        return values

    @staticmethod
    def _survey_numbers(context: Dict[str, Any]) -> List[str]:
        numbers = ReportGenerationService._distinct(context, "survey_number")
        case_survey = _text(context["case"].get("survey_number"))
        if case_survey and case_survey not in numbers:
            numbers.insert(0, case_survey)
        return numbers

    @staticmethod
    def _open_flags(context: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [f for f in context["flags"] if _text(f.get("status")) in ("", "raised", "open")]

    # ---- title search draft ------------------------------------------

    def _title_search_draft(self, context: Dict[str, Any]) -> ReportDraft:
        case = context["case"]
        name = case.get("property_name") or case.get("title") or "Property"
        sections: List[DraftSection] = []

        locations = self._distinct(context, "property_location")
        areas = self._distinct(context, "area")
        boundaries = self._distinct(context, "property_boundaries")
        sections.append(DraftSection(id="property", heading="Property under scrutiny", blocks=[
            DraftBlock(type="table", columns=["Item", "Details"], rows=[
                ["Property", name],
                ["Location", case.get("location") or "; ".join(locations)],
                ["Survey / plot number(s)", ", ".join(self._survey_numbers(context))],
                ["Area", "; ".join(areas)],
                ["Boundaries", "; ".join(boundaries)],
                ["Date of report", _today_text()],
            ]),
        ]))

        sections.append(DraftSection(id="documents", heading="Documents examined", blocks=[
            DraftBlock(type="table", columns=["Sr.", "Document", "Type", "Date", "Registration no."], rows=[
                [
                    str(index),
                    document.get("file_name") or "",
                    _titlecase(_text(context["fields_by_doc"][document["id"]].get("document_type"))),
                    _text(context["fields_by_doc"][document["id"]].get("transaction_date")),
                    _text(context["fields_by_doc"][document["id"]].get("registration_number")),
                ]
                for index, document in enumerate(context["documents"], start=1)
            ]),
        ]))

        chain_rows = [
            [str(i), _text(link.get("owner")), _text(link.get("date")), _text(link.get("type")),
             _text(link.get("survey")), link.get("source") or ""]
            for i, link in enumerate(context["chain"], start=1)
        ]
        chain_blocks = [DraftBlock(
            type="table",
            columns=["Sr.", "Owner", "Date", "Mode of transfer", "Survey no.", "Source document"],
            rows=chain_rows,
        )] if chain_rows else [DraftBlock(type="paragraph", text="No ownership transfers were extracted from the approved documents.")]
        sections.append(DraftSection(id="chain", heading="Chain of title", blocks=chain_blocks))

        flag_rows = [
            [_titlecase(_text(f.get("flag_type"))), _text(f.get("severity")).capitalize(),
             _text(f.get("description")), _text(f.get("status")).capitalize()]
            for f in context["flags"]
        ]
        sections.append(DraftSection(id="flags", heading="Observations and risk flags", blocks=[
            DraftBlock(type="table", columns=["Issue", "Severity", "Details", "Status"], rows=flag_rows)
            if flag_rows else DraftBlock(type="paragraph", text="No risk flags were raised for this case."),
        ]))

        extract_blocks: List[DraftBlock] = []
        for index, excerpt in enumerate(context["excerpts"], start=1):
            label = f"{index}. {excerpt.get('document_name') or excerpt.get('document_id')} - page {excerpt.get('page_number')}"
            extract_blocks.append(DraftBlock(type="paragraph", text=label))
            for block in split_blocks(excerpt.get("excerpt_text") or ""):
                if block["type"] == "table":
                    extract_blocks.append(DraftBlock(type="table", columns=block["columns"], rows=block["rows"]))
                else:
                    extract_blocks.append(DraftBlock(type="paragraph", text=block["text"]))
            if excerpt.get("note"):
                extract_blocks.append(DraftBlock(type="paragraph", text=f"Note: {excerpt['note']}"))
        if not extract_blocks:
            extract_blocks.append(DraftBlock(type="paragraph", text="No extracts were selected for this report."))
        sections.append(DraftSection(id="extracts", heading="Extracts relied on", blocks=extract_blocks))

        sections.append(DraftSection(id="opinion", heading="Opinion", blocks=[
            DraftBlock(type="paragraph", text=OPINION_PLACEHOLDER),
        ]))
        sections.append(DraftSection(id="signature", heading="Signed", blocks=[
            DraftBlock(type="paragraph", text=f"Place: ____________________    Date: {_today_text()}"),
            DraftBlock(type="paragraph", text="Advocate"),
        ]))

        return ReportDraft(
            format_id=report_formats.TITLE_SEARCH_ID,
            kind="title_search",
            title="Title Search Report",
            warnings=self._warnings(context, extra_open_flag_note=True),
            sections=sections,
        )

    # ---- bank format draft -------------------------------------------

    def _bank_draft(self, format_id: str, context: Dict[str, Any]) -> ReportDraft:
        manifest = report_formats.get_manifest(format_id)
        prefill = self._prefill_values(context)
        warnings = self._warnings(context)

        answers: Dict[str, Any] = {"fields": {}, "loops": {}}
        try:
            answers = self._autofill(manifest, self._documents_for_autofill(context))
        except Exception:
            logger.exception("report.autofill_failed | format_id=%s", format_id)
            warnings.append(
                "The documents could not be read automatically just now, so only a few fields are filled. "
                "Use Rebuild to try again, or fill the form yourself."
            )

        fields: List[DraftField] = []
        for spec in manifest.get("fields", []):
            must_confirm = spec.get("review_level") == "must_confirm"
            value = "" if must_confirm else (
                # The model writes English (it transliterates Marathi names); the
                # rule-based fill copies the document's own script, so it is the fallback.
                answers["fields"].get(spec["name"]) or prefill.get(spec["name"], "")
            )
            fields.append(DraftField(
                name=spec["name"],
                label=spec.get("description") or _titlecase(spec["name"]),
                type=spec.get("type", "text"),
                options=[str(o) for o in spec.get("options", [])],
                source=spec.get("source", ""),
                review_level=spec.get("review_level", ""),
                required=bool(spec.get("required")),
                value=value,
                group=FIELD_GROUPS.get(spec.get("source", ""), "Other"),
                suggested=bool(value) and spec["name"] != "report_date",
            ))
        group_order = list(FIELD_GROUPS.values()) + ["Other"]
        fields.sort(key=lambda f: (group_order.index(f.group), f.label.lower()))

        loops: List[DraftLoop] = []
        for spec in manifest.get("loops", []):
            item_fields = list(spec.get("item_fields", []))
            nested = {k: v for k, v in (spec.get("nested_lists") or {}).items()}
            answered_rows = answers["loops"].get(spec["name"]) if spec.get("review_level") != "must_confirm" else None
            rows = answered_rows or self._prefill_loop_rows(spec, item_fields, nested, context)
            loops.append(DraftLoop(
                name=spec["name"],
                label=spec.get("description") or _titlecase(spec["name"]),
                item_fields=item_fields,
                nested_lists=nested,
                rows=rows,
                suggested=bool(answered_rows),
            ))

        fillable = [f for f in fields if f.review_level != "must_confirm" and f.source != "profile"]
        filled = sum(1 for f in fillable if f.suggested)
        if filled:
            warnings.insert(
                0,
                f"{filled} of {len(fillable)} factual fields were filled from your approved documents. "
                "Check each one against the documents; the rest are for you to complete.",
            )

        return ReportDraft(
            format_id=format_id,
            kind="bank",
            title=f"{manifest.get('bank', format_id)} - title report",
            bank=manifest.get("bank"),
            warnings=warnings,
            fields=fields,
            loops=loops,
        )

    def _documents_for_autofill(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        documents = []
        for document in context["documents"]:
            fields = {
                key: value
                for key, value in context["fields_by_doc"][document["id"]].items()
                if key != "full_text" and not key.endswith("_confidence") and value not in (None, "", [])
            }
            pages = sorted(
                self.generic_repo.select("document_pages", {"document_id": document["id"]}),
                key=lambda page: page.get("page_number") or 0,
            )
            text = "\n\n".join(
                f"[Page {page.get('page_number')}]\n{page.get('original_text') or ''}"
                + (f"\n(English) {page['english_text']}" if page.get("english_text") else "")
                for page in pages
            )
            documents.append({"name": document.get("file_name") or document["id"], "fields": fields, "text": text})
        return documents

    def _prefill_values(self, context: Dict[str, Any]) -> Dict[str, str]:
        chain = context["chain"]
        current_owner = _text(chain[-1].get("owner")) if chain else ""
        if not current_owner:
            owners = self._distinct(context, "owner_name")
            current_owner = owners[-1] if owners else ""
        previous_owner = _text(chain[-2].get("owner")) if len(chain) > 1 else ""
        if not previous_owner:
            previous = self._distinct(context, "previous_owner_name")
            previous_owner = previous[-1] if previous else ""

        surveys = self._survey_numbers(context)
        description_parts = [
            "; ".join(self._distinct(context, "property_location")) or _text(context["case"].get("location")),
            ("Survey no. " + ", ".join(surveys)) if surveys else "",
            "; ".join(self._distinct(context, "area")),
        ]
        values = {
            "mortgagor_name": current_owner,
            "present_owner_names": current_owner,
            "record_owner_name": current_owner,
            "land_owner_names": current_owner,
            "transferor_names": previous_owner,
            "gat_numbers": ", ".join(surveys),
            "property_description": ", ".join(p for p in description_parts if p),
            "report_date": _today_text(),
        }
        return {k: v for k, v in values.items() if v}

    @staticmethod
    def _prefill_loop_rows(
        spec: Dict[str, Any], item_fields: List[str], nested: Dict[str, str], context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        def blank_row() -> Dict[str, Any]:
            row: Dict[str, Any] = {name: "" for name in item_fields}
            row.update({name: [] for name in nested})
            return row

        surveys = ReportGenerationService._survey_numbers(context)
        if "gat_number" in item_fields and surveys:
            rows = []
            for number in surveys:
                row = blank_row()
                row["gat_number"] = number
                rows.append(row)
            return rows
        return [blank_row() for _ in range(max(1, int(spec.get("min_items") or 1)))]

    @staticmethod
    def _warnings(context: Dict[str, Any], extra_open_flag_note: bool = False) -> List[str]:
        warnings: List[str] = []
        open_flags = ReportGenerationService._open_flags(context)
        if open_flags:
            warnings.append(
                f"{len(open_flags)} risk flag(s) are still open on this case. Review them before you write the opinion."
            )
        if not context["excerpts"] and extra_open_flag_note:
            warnings.append("No text was selected from the documents, so the extracts section is empty.")
        return warnings

    # ---- export --------------------------------------------------------

    def export(self, case_id: str, draft: ReportDraft, file_type: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        self.doc_service.authorize_case_access(case_id, current_user)
        if draft.kind == "bank":
            report_formats.get_manifest(draft.format_id)  # rejects an unknown id
        elif not report_formats.is_title_search(draft.format_id):
            raise PropertySystemException("Unknown report format", status_code=422)

        stem = _safe_filename(draft.title)
        if file_type == "docx":
            return {"content": render_docx(draft), "filename": f"{stem}.docx", "media_type": DOCX_MEDIA_TYPE}
        return {"content": render_pdf(draft), "filename": f"{stem}.pdf", "media_type": "application/pdf"}


DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _safe_filename(title: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in " -_" else " " for ch in title).strip()
    return "-".join(cleaned.split())[:80] or "report"


# ---- rendering ---------------------------------------------------------

def render_docx(draft: ReportDraft) -> bytes:
    if draft.kind == "bank":
        return _render_bank_docx(draft)
    return _render_title_search_docx(draft)


def render_pdf(draft: ReportDraft) -> bytes:
    if draft.kind == "bank":
        return _convert_docx_to_pdf(_render_bank_docx(draft))
    from app.services.report_pdf_builder import build_draft_pdf

    return build_draft_pdf(draft)


def _render_title_search_docx(draft: ReportDraft) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    document = Document()
    title = document.add_heading(draft.title.upper(), level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for section in draft.sections:
        document.add_heading(section.heading, level=1)
        for block in section.blocks:
            if block.type == "table" and block.columns:
                table = document.add_table(rows=1, cols=len(block.columns))
                table.style = "Table Grid"
                for index, column in enumerate(block.columns):
                    cell = table.rows[0].cells[index]
                    cell.text = column
                    for run in cell.paragraphs[0].runs:
                        run.bold = True
                for row in block.rows:
                    cells = table.add_row().cells
                    for index in range(len(block.columns)):
                        cells[index].text = row[index] if index < len(row) else ""
                document.add_paragraph()
            else:
                for line in (block.text or "").split("\n"):
                    document.add_paragraph(line)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def bank_template_context(draft: ReportDraft) -> Dict[str, Any]:
    """The values handed to the bank's docxtpl template: every field by name,
    every repeating table as a list of rows, nested lists as lists of strings."""
    context: Dict[str, Any] = {field.name: field.value for field in draft.fields}
    for loop in draft.loops:
        rows = []
        for row in loop.rows:
            rendered: Dict[str, Any] = {}
            for name in loop.item_fields:
                rendered[name] = _text(row.get(name))
            for name in loop.nested_lists:
                value = row.get(name) or []
                if isinstance(value, str):
                    value = value.split("\n")
                rendered[name] = [_text(v) for v in value if _text(v)]
            if any(rendered.values()):
                rows.append(rendered)
        context[loop.name] = rows
    return context


def _render_bank_docx(draft: ReportDraft) -> bytes:
    from docxtpl import DocxTemplate

    template = DocxTemplate(str(report_formats.template_path(draft.format_id)))
    template.render(bank_template_context(draft), autoescape=True)
    buffer = io.BytesIO()
    template.save(buffer)
    return buffer.getvalue()


def _find_pdf_converter() -> Optional[str]:
    for name in PDF_CONVERTER_NAMES:
        found = shutil.which(name)
        if found:
            return found
    return None


def _convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    converter = _find_pdf_converter()
    if converter is None:
        raise PropertySystemException(
            "PDF for bank formats needs LibreOffice on the server, which is not installed here. "
            "Download the Word file instead.",
            status_code=501,
        )
    with tempfile.TemporaryDirectory() as workdir:
        source = Path(workdir) / "report.docx"
        source.write_bytes(docx_bytes)
        try:
            subprocess.run(
                [converter, "--headless", "--convert-to", "pdf", "--outdir", workdir, str(source)],
                check=True,
                capture_output=True,
                timeout=PDF_CONVERSION_TIMEOUT_SECONDS,
            )
        except (subprocess.SubprocessError, OSError):
            logger.exception("report.pdf_conversion_failed")
            raise PropertySystemException("The PDF could not be created. Download the Word file instead.", status_code=502)
        output = Path(workdir) / "report.pdf"
        if not output.exists():
            raise PropertySystemException("The PDF could not be created. Download the Word file instead.", status_code=502)
        return output.read_bytes()
