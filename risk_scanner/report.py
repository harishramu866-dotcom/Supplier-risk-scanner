"""Stage 5: report summary (see report_summary.md).

Takes the completed report (all five categories + overall_risk from stage
4's scoring) and asks Claude to write the human-readable summary and
completeness note, then assembles and saves the full SupplierRiskReport.
"""

import json
import os
import re
from datetime import date, datetime

import anthropic
from dotenv import load_dotenv

from risk_scanner.json_utils import parse_json_object
from risk_scanner.scoring import compute_overall_risk
from risk_scanner.validation import validate_report

load_dotenv()

OUTPUT_DIR = "output"

SUMMARY_PROMPT = """Write a short risk summary for this supplier, based only on the
structured findings below. Do not add any new claims — only summarize
what's already here.

Supplier: {supplier_name}
Overall risk: {overall_risk}
Categories: {categories_json}

Write two things:

1. summary: one paragraph (3-4 sentences) a compliance reviewer could read
   in five seconds. Lead with the most serious finding if there is one.
   Mention which categories were clear. Plain language, no jargon.

2. data_completeness_note: one sentence flagging any category marked
   "Unknown" and what that means for how much to trust this report. If
   nothing is Unknown, state that all five categories were checked.

Output as JSON:
{{ "summary": "...", "data_completeness_note": "..." }}"""


def generate_summary(
    supplier_name: str,
    overall_risk: str,
    categories: dict,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Stage 5: write the summary + completeness note. Sees only structured findings, never raw search results."""
    client = client or anthropic.Anthropic()
    prompt = SUMMARY_PROMPT.format(
        supplier_name=supplier_name,
        overall_risk=overall_risk,
        categories_json=json.dumps(categories, indent=2),
    )

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    result = parse_json_object(text)

    missing = [key for key in ("summary", "data_completeness_note") if key not in result]
    if missing:
        raise ValueError(f"model output missing fields: {missing}\nraw output: {text}")

    return result


def assemble_report(supplier_name: str, categories: dict) -> dict:
    """Stage 4 + 5: score the categories, write the summary, assemble the full SupplierRiskReport."""
    overall_risk = compute_overall_risk(categories)
    summary_fields = generate_summary(supplier_name, overall_risk, categories)

    report = {
        "supplier_name": supplier_name,
        "search_date": date.today().isoformat(),
        "overall_risk": overall_risk,
        "categories": categories,
        "summary": summary_fields["summary"],
        "data_completeness_note": summary_fields["data_completeness_note"],
    }
    validate_report(report)
    return report


def save_report(report: dict, output_dir: str = OUTPUT_DIR) -> str:
    """Save the full report to output/<supplier>_report_<timestamp>.json. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", report["supplier_name"].lower()).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{slug}_report_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return path
