from app.services.llm_extractor import extract_from_image_path
from app.services.validation import validate_extraction
import json
import sys

if len(sys.argv) < 2:
    print("Usage: python test_extraction.py path/to/image.jpg")
    sys.exit(1)

image_path = sys.argv[1]
print(f"Testing extraction on: {image_path}")
print("-" * 50)

result = extract_from_image_path(image_path)

if result["success"]:
    e = result["extracted"]
    print("SUCCESS\n")
    print("FULL TEXT (verbatim):")
    print(e.get("full_text", "MISSING"))
    print("\n" + "-" * 50)
    print("STRUCTURED FIELDS:\n")
    print(json.dumps(e, indent=2, ensure_ascii=False))

    validation_result = validate_extraction(e)
    print("\n" + "-" * 50)
    print("VALIDATION RESULT:")
    print(json.dumps(validation_result, indent=2))

    print("\n" + "-" * 50)
    print(f"Overall confidence: {e.get('overall_confidence')}")
    print(f"Has handwritten content: {e.get('has_handwritten_content')}")
    print(f"Needs human review: {validation_result['needs_human_review']}")
    print(f"Model: {result['model_used']}")
else:
    print("FAILED")
    print(f"Error: {result['error']}")
    print(f"Raw output: {result['raw_output']}")