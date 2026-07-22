from app.services.llm_extractor import extract_from_image_path
import json
import sys

if len(sys.argv) < 2:
    print("Usage: python test_extraction.py path/to/image.jpg")
    sys.exit(1)

result = extract_from_image_path(sys.argv[1])

if result["success"]:
    print("SUCCESS")
    print(json.dumps(result["extracted"], indent=2, ensure_ascii=False))
    print(f"\nConfidence: {result['extracted'].get('confidence')}")
    print(f"Model: {result['model_used']}")
else:
    print("FAILED")
    print(f"Error: {result['error']}")
    print(f"Raw output: {result['raw_output']}")