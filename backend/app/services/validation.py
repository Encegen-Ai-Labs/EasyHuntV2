from typing import Dict, Any, List
from datetime import datetime


def _is_low_quality(confidence: str) -> bool:
    return confidence in (None, "low")


def validate_extraction(extracted: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    warnings: List[str] = []

    # required fields present at all
    required = ["document_type", "language_detected", "full_text"]
    for field in required:
        if not extracted.get(field):
            errors.append(f"Missing required field: {field}")

    # date sanity check
    date_str = extracted.get("transaction_date")
    if date_str:
        try:
            parsed_date = datetime.strptime(date_str, "%Y-%m-%d")
            if parsed_date.year < 1900 or parsed_date > datetime.now():
                warnings.append(f"transaction_date looks implausible: {date_str}")
        except ValueError:
            errors.append(f"transaction_date not in YYYY-MM-DD format: {date_str}")

    # validate dates inside chain entries too
    chain = extracted.get("chain", [])
    for i, record in enumerate(chain):
        chain_date = record.get("date")
        if chain_date:
            try:
                parsed = datetime.strptime(chain_date, "%Y-%m-%d")
                if parsed.year < 1900 or parsed > datetime.now():
                    warnings.append(f"chain[{i}] date looks implausible: {chain_date}")
            except ValueError:
                errors.append(f"chain[{i}] date not in valid YYYY-MM-DD format: {chain_date}")
    
    # survey number shouldn't be empty string vs null confusion
    survey = extracted.get("survey_number")
    if survey == "":
        warnings.append("survey_number is empty string, should be null")

    # collect low-confidence fields for review flagging
    low_confidence_fields = []
    for key in list(extracted.keys()):
        if key.endswith("_confidence") and _is_low_quality(extracted[key]):
            field_name = key.replace("_confidence", "")
            low_confidence_fields.append(field_name)

    overall_conf = extracted.get("overall_confidence")

    # Missing handwriting detection is treated conservatively and sent for review.
    is_handwritten = extracted.get("has_handwritten_content", True)
    if is_handwritten:
        warnings.append("Document contains handwritten content — flagged for review regardless of confidence")

    needs_review = (
        bool(errors)
        or bool(low_confidence_fields)
        or _is_low_quality(overall_conf)
        or is_handwritten
    )

    return {
        "is_valid": len(errors) == 0,
        "needs_human_review": needs_review,
        "reason_handwritten": is_handwritten,
        "errors": errors,
        "warnings": warnings,
        "low_confidence_fields": low_confidence_fields
    }