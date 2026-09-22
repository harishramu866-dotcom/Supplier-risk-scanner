"""Manual test for stage 3 (extraction): run it on a real stage 2 output and print the result.

Every run saves its result to output/<supplier>_extraction_<timestamp>.json.

Usage: py scripts/run_extraction.py [path/to/stage2_output.json]
If no path is given, uses the most recently modified file in output/.
"""

import json
import sys
from pathlib import Path

from risk_scanner.extraction import extract_category_findings, save_extraction_result
from risk_scanner.validation import is_valid_category_result


def _latest_output_file() -> Path:
    # exclude stage 3's own "*_extraction_*" files — this looks for a stage 2 input
    candidates = sorted(
        (p for p in Path("output").glob("*.json") if "_extraction_" not in p.name),
        key=lambda p: p.stat().st_mtime,
    )
    if not candidates:
        raise FileNotFoundError("no stage 2 output found in output/ — run scripts/run_search_agent.py first")
    return candidates[-1]


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_output_file()
    print(f"=== Using stage 2 output: {input_path} ===\n")

    with open(input_path, "r", encoding="utf-8") as f:
        stage2 = json.load(f)

    supplier_name = stage2["supplier_name"]
    raw_results = stage2["raw_results"]

    categories = {}
    for category, results_for_category in raw_results.items():
        print(f"=== Extracting: {category} ===")
        result = extract_category_findings(supplier_name, category, results_for_category)
        print(json.dumps(result, indent=2))
        print(f"Schema valid: {is_valid_category_result(result)}")
        print()
        categories[category] = result

    path = save_extraction_result(supplier_name, categories)
    print(f"Saved to {path}")


if __name__ == "__main__":
    main()
