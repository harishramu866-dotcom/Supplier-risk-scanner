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

from risk_scanner.context import clean_context
from risk_scanner.json_utils import parse_json_object
from risk_scanner.scoring import compute_overall_risk
from risk_scanner.validation import validate_report

load_dotenv()

REPORTS_DIR = "reports"

SUMMARY_PROMPT = """Write a short risk summary for this supplier, based only on the
structured findings below. Do not add any new claims — only summarize
what's already here.

Supplier: {supplier_name}
Overall risk: {overall_risk}
{identity_block}Categories: {categories_json}

Write two things:

1. summary: one paragraph (3-4 sentences) a compliance reviewer could read
   in five seconds. Lead with the most serious finding if there is one.
   Mention which categories were clear. Plain language, no jargon.
   If an identity check is shown above and its status is Ambiguous or
   Unverified, add one more sentence saying so (Ambiguous: findings could not
   be attributed to a single company; Unverified: the company's identity was
   not confirmed), so a reader never assumes the right company was confirmed.
   If the status is Confirmed, or no identity check is shown, do not mention it.

2. data_completeness_note: one sentence flagging any category marked
   "Unknown" and what that means for how much to trust this report. If
   nothing is Unknown, state that all five categories were checked.

Output as JSON:
{{ "summary": "...", "data_completeness_note": "..." }}"""


def generate_summary(
    supplier_name: str,
    overall_risk: str,
    categories: dict,
    identity_check: dict | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Stage 5: write the summary + completeness note. Sees only structured findings, never raw search results."""
    client = client or anthropic.Anthropic()
    identity_block = (
        f"Identity check: {identity_check['status']} - {identity_check['note']}\n" if identity_check else ""
    )
    prompt = SUMMARY_PROMPT.format(
        supplier_name=supplier_name,
        overall_risk=overall_risk,
        identity_block=identity_block,
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


def assemble_report(
    supplier_name: str,
    categories: dict,
    supplier_context: dict | None = None,
    identity_check: dict | None = None,
) -> dict:
    """Stage 4 + 5: score the categories, write the summary, assemble the full SupplierRiskReport.

    supplier_context and identity_check are optional and omitted from the report when not given.
    """
    overall_risk = compute_overall_risk(categories)
    summary_fields = generate_summary(supplier_name, overall_risk, categories, identity_check)

    report = {
        "supplier_name": supplier_name,
        "search_date": date.today().isoformat(),
        "overall_risk": overall_risk,
    }
    cleaned_context = clean_context(supplier_context)
    if cleaned_context:
        report["supplier_context"] = cleaned_context
    if identity_check:
        report["identity_check"] = identity_check
    report.update(
        categories=categories,
        summary=summary_fields["summary"],
        data_completeness_note=summary_fields["data_completeness_note"],
    )
    validate_report(report)
    return report


def save_report(report: dict, output_dir: str = REPORTS_DIR) -> str:
    """Save the full report to reports/<supplier>_report_<timestamp>.json. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", report["supplier_name"].lower()).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{slug}_report_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    return path
