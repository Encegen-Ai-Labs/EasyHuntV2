from google import genai
from typing import Dict, Any, List
import os
from dotenv import load_dotenv

load_dotenv()

client_genai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

REPORT_PROMPT_TEMPLATE = """You are drafting a property due diligence report for a legal reviewer in India. Based on the data below, write a clear, professional draft report.

CASE DATA:
Documents reviewed: {document_count}
Ownership chain: {chain_summary}
Risk flags raised: {flags_summary}

Write the report with these sections:
1. Summary of documents reviewed
2. Ownership history (chronological)
3. Risk flags and concerns (list each clearly, do not soften or omit any)
4. Overall assessment (state clearly this is a DRAFT requiring lawyer review, do not present it as a final legal opinion)

Keep the tone factual and precise. Do not make definitive legal conclusions - this draft is for a lawyer to review, correct, and approve, not for direct use."""


def generate_draft_report(
    case_id: str,
    document_count: int,
    chain_records: List[Dict[str, Any]],
    flags: List[Dict[str, Any]]
) -> Dict[str, Any]:
    try:
        chain_summary = "\n".join([
            f"- {r.get('owner_name')} (from {r.get('transaction_date')}, {r.get('transaction_type')}, survey {r.get('survey_number')})"
            for r in chain_records
        ]) or "No ownership chain records found."

        flags_summary = "\n".join([
            f"- [{f.get('severity', 'unknown').upper()}] {f.get('flag_type')}: {f.get('description')}"
            for f in flags
        ]) or "No risk flags raised."

        prompt = REPORT_PROMPT_TEMPLATE.format(
            document_count=document_count,
            chain_summary=chain_summary,
            flags_summary=flags_summary
        )

        response = client_genai.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[prompt]
        )

        return {
            "success": True,
            "draft_text": response.text,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "draft_text": None,
            "error": str(e)
        }