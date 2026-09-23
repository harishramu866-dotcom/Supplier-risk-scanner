"""Manual test for stage 4+5 (scoring + report summary): assemble the final report and print it.

Every run saves its result to output/<supplier>_report_<timestamp>.json.

Usage: py scripts/run_report.py [path/to/stage3_extraction_output.json]
If no path is given, uses the most recently modified "*_extraction_*.json" file in output/.
"""

import json
import sys
from pathlib import Path

from risk_scanner.report import assemble_report, save_report


def _latest_extraction_file() -> Path:
    candidates = sorted(Path("output").glob("*_extraction_*.json"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError("no stage 3 output found in output/ — run scripts/run_extraction.py first")
    return candidates[-1]


def main():
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _latest_extraction_file()
    print(f"=== Using stage 3 output: {input_path} ===\n")

    with open(input_path, "r", encoding="utf-8") as f:
        stage3 = json.load(f)

    supplier_name = stage3["supplier_name"]
    categories = stage3["categories"]

    report = assemble_report(supplier_name, categories)
    print(json.dumps(report, indent=2))

    path = save_report(report)
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
