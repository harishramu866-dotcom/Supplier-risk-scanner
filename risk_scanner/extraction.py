"""Stage 3: extraction (see extraction.md), the core AI step.

Takes raw search results for one category and asks Claude to decide what's
a genuine finding versus noise, producing {status, findings} that matches
the "category" definition in risk_report.schema.json.
"""

import json
import os
import re
from datetime import datetime

import anthropic
from dotenv import load_dotenv

from risk_scanner.json_utils import parse_json_object
from risk_scanner.validation import validate_category_result

load_dotenv()

OUTPUT_DIR = "output"

EXTRACTION_PROMPT = """You are extracting compliance risk findings from web search results about
a supplier. Review the results below and determine the status of this
category for this supplier.

Supplier: {supplier_name}
Category: {category}  (one of: labor, environmental, sanctions, financial, legal)
Search results:
{results_block}

Instructions:
1. First, verify relevance. Some results may be about a different company
   with a similar name, or may not actually be about {category} at all.
   Discard anything that isn't clearly about THIS supplier and THIS category.
2. For each genuine, relevant finding, write:
   - claim: a one-sentence factual statement of what was found (not your
     opinion — just what the source says happened)
   - source: the exact URL it came from
   - confidence: "High" if the source is authoritative (news outlet, gov
     filing, official report) and the claim is specific; "Medium" if the
     source is less authoritative or the claim is vague; "Low" if you're
     genuinely unsure this is reliable
3. Set status for the category:
   - "Flagged" if you have one or more genuine findings
   - "Clear" if you found relevant, reliable results and none show a problem
   - "Unknown" if search results were empty, irrelevant, or too unreliable
     to conclude anything — DO NOT default to "Clear" just because you
     found nothing. Absence of evidence is not evidence of absence.

Do not invent findings that aren't supported by the search results. Do not
merge or restate the same underlying incident as multiple findings.

Output as JSON matching this shape:
{{
  "status": "Clear" | "Flagged" | "Unknown",
  "findings": [
    {{ "claim": "...", "source": "https://...", "confidence": "Low" | "Medium" | "High" }}
  ]
}}"""


def _format_results_block(results_for_category: dict) -> str:
    """results_for_category: {query: [{title, snippet, url}, ...]} as produced by stage 2."""
    lines = []
    for hits in results_for_category.values():
        for hit in hits:
            lines.append(f"- Title: {hit['title']}\n  Snippet: {hit['snippet']}\n  URL: {hit['url']}")
    return "\n".join(lines) if lines else "(no search results returned)"


def extract_category_findings(
    supplier_name: str,
    category: str,
    results_for_category: dict,
    client: anthropic.Anthropic | None = None,
) -> dict:
    client = client or anthropic.Anthropic()
    prompt = EXTRACTION_PROMPT.format(
        supplier_name=supplier_name,
        category=category,
        results_block=_format_results_block(results_for_category),
    )

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    result = parse_json_object(text)
    validate_category_result(result)
    return result


def save_extraction_result(supplier_name: str, categories: dict, output_dir: str = OUTPUT_DIR) -> str:
    """Save a stage 3 result to output/<supplier>_extraction_<timestamp>.json. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", supplier_name.lower()).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{slug}_extraction_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"supplier_name": supplier_name, "categories": categories}, f, indent=2)
    return path


def extract_all_categories(supplier_name: str, raw_results: dict) -> dict:
    """Run extraction once per category, save the combined result to output/, and return it.

    raw_results: stage 2's {category: {query: [hits]}}.
    """
    categories = {
        category: extract_category_findings(supplier_name, category, results_for_category)
        for category, results_for_category in raw_results.items()
    }
    save_extraction_result(supplier_name, categories)
    return categories
