from google import genai
from google.genai import types
import json
import os
import tempfile
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

client_genai = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

EXTRACTION_PROMPT = """You are an expert at reading Indian property documents including handwritten text in Hindi, Marathi, Tamil, Telugu, Kannada and other Indian regional languages.

Extract the following fields from this property document image and return ONLY a valid JSON object. No explanation, no preamble, no markdown backticks, just raw JSON.

{
  "document_type": "sale_deed | mutation_record | tax_receipt | encumbrance_certificate | other",
  "owner_name": "full name of current owner or null",
  "previous_owner_name": "full name of previous owner or null",
  "survey_number": "property survey or plot number or null",
  "transaction_date": "date in YYYY-MM-DD format or null",
  "transaction_type": "sale | inheritance | gift | partition | other",
  "property_location": "address or location description or null",
  "property_boundaries": "boundary description or null",
  "area": "property area with unit or null",
  "registration_number": "document registration number or null",
  "language_detected": "primary language of the document",
  "confidence": "high | medium | low",
  "unreadable_sections": "describe unclear sections or null",
  "chain": [
    {
      "order": 1,
      "owner": "owner name",
      "date": "YYYY-MM-DD",
      "type": "Sale Deed | Mutation | Gift | Inheritance | other",
      "survey": "survey number"
    }
  ]
}

Rules:
- Return ONLY the JSON object, nothing else
- No markdown backticks
- No explanation before or after
- If a field is not present or not readable use null
- chain array should contain all ownership transfers visible in the document in chronological order
- For confidence: high means everything clearly readable, medium means some parts unclear, low means significant portions unreadable"""


def _clean_json_response(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return raw.strip()


def extract_from_image_path(image_path: str) -> Dict[str, Any]:
    raw_output = None
    try:
        with open(image_path, "rb") as f:
            image_bytes = f.read()

        response = client_genai.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/jpeg"
                ),
                EXTRACTION_PROMPT
            ]
        )

        raw_output = response.text
        cleaned = _clean_json_response(raw_output)
        extracted = json.loads(cleaned)

        return {
            "success": True,
            "raw_output": raw_output,
            "extracted": extracted,
            "model_used": "gemini-2.0-flash",
            "error": None
        }

    except json.JSONDecodeError:
        return {
            "success": False,
            "raw_output": raw_output,
            "extracted": None,
            "model_used": "gemini-2.0-flash",
            "error": "Model returned invalid JSON"
        }
    except Exception as e:
        return {
            "success": False,
            "raw_output": None,
            "extracted": None,
            "model_used": "gemini-2.0-flash",
            "error": str(e)
        }


def extract_from_supabase_url(file_url: str) -> Dict[str, Any]:
    raw_output = None
    try:
        import httpx
        with httpx.Client() as client:
            response = client.get(file_url)
            response.raise_for_status()

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".jpg"
        ) as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name

        result = extract_from_image_path(tmp_path)
        os.unlink(tmp_path)
        return result

    except Exception as e:
        return {
            "success": False,
            "raw_output": None,
            "extracted": None,
            "model_used": "gemini-2.0-flash",
            "error": str(e)
        }