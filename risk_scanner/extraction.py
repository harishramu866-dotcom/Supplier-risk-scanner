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

from risk_scanner.context import clean_context, format_context_block
from risk_scanner.identity import combine_identity_checks, normalize_identity
from risk_scanner.json_utils import parse_json_object
from risk_scanner.validation import validate_category_result

load_dotenv()

OUTPUT_DIR = "output"

EXTRACTION_PROMPT = """You are extracting compliance risk findings from web search results about
a supplier. Review the results below and determine the status of this
category for this supplier.

Supplier: {supplier_name}
{context_block}
Category: {category}  (one of: labor, environmental, sanctions, financial, legal)
Search results:
{results_block}

Instructions:
1. First, verify relevance and identity. Some results may be about a
   different company with a similar name, or may not actually be about
   {category} at all.
   - Compare each result against the supplied context (country, website
     domain, industry, parent company, city), when there is any. Discard
     results that clearly point to a different entity: a different country,
     a different website domain, a different industry, or a different parent
     company.
   - Do NOT discard a result just because it leaves a context detail out.
     News articles often omit the city or industry; only a clear mismatch is
     evidence of a different company.
   - Discard anything that isn't clearly about THIS supplier and THIS category.
2. Decide identity_check.status:
   - "Ambiguous" if the results suggest two or more plausible, different
     companies and the supplied context cannot tell which one is the
     supplier. Do NOT attribute findings to either company: return
     "findings": [] and "status": "Unknown" for this category, and say why
     in the note.
   - "Confirmed" only if something concrete supports that the results you
     kept are about the supplied company: a matching website domain,
     country, or parent company. Name what matched in the note. A matching
     name alone is not enough.
   - "Unverified" in every other case, and always if no context was supplied.
   The note is one sentence explaining why.
3. For each genuine, relevant finding, write:
   - claim: a one-sentence factual statement of what was found (not your
     opinion — just what the source says happened)
   - source: the exact URL it came from
   - confidence: "High" if the source is authoritative (news outlet, gov
     filing, official report) and the claim is specific; "Medium" if the
     source is less authoritative or the claim is vague; "Low" if you're
     genuinely unsure this is reliable
4. Set status for the category:
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
  ],
  "identity_check": {{ "status": "Confirmed" | "Ambiguous" | "Unverified", "note": "..." }}
}}"""


def _format_results_block(results_for_category: dict) -> str:
    """results_for_category: {query: [{title, snippet, url}, ...]} as produced by stage 2."""
    lines = []
    for hits in results_for_category.values():
        for hit in hits:
            lines.append(f"- Title: {hit['title']}\n  Snippet: {hit['snippet']}\n  URL: {hit['url']}")
    return "\n".join(lines) if lines else "(no search results returned)"


def extract_category_with_identity(
    supplier_name: str,
    category: str,
    results_for_category: dict,
    context: dict | None = None,
    client: anthropic.Anthropic | None = None,
) -> tuple[dict, dict]:
    """Returns (category result, this category's identity_check).

    An Ambiguous identity forces the category to Unknown with no findings, even if the
    model returned some, so findings are never attributed to either candidate company.
    """
    client = client or anthropic.Anthropic()
    prompt = EXTRACTION_PROMPT.format(
        supplier_name=supplier_name,
        context_block=format_context_block(context),
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
    identity = normalize_identity(result.pop("identity_check", None), context)
    if identity["status"] == "Ambiguous":
        result = {"status": "Unknown", "findings": []}
    validate_category_result(result)
    return result, identity


def extract_category_findings(
    supplier_name: str,
    category: str,
    results_for_category: dict,
    context: dict | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    return extract_category_with_identity(supplier_name, category, results_for_category, context, client)[0]


def save_extraction_result(
    supplier_name: str,
    categories: dict,
    supplier_context: dict | None = None,
    identity_check: dict | None = None,
    output_dir: str = OUTPUT_DIR,
) -> str:
    """Save a stage 3 result to output/<supplier>_extraction_<timestamp>.json. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", supplier_name.lower()).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{slug}_extraction_{timestamp}.json")

    result = {"supplier_name": supplier_name}
    cleaned = clean_context(supplier_context)
    if cleaned:
        result["supplier_context"] = cleaned
    if identity_check:
        result["identity_check"] = identity_check
    result["categories"] = categories

    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return path


def extract_all_categories(
    supplier_name: str, raw_results: dict, context: dict | None = None
) -> tuple[dict, dict]:
    """Run extraction once per category, save the combined result to output/.

    raw_results: stage 2's {category: {query: [hits]}}. Returns (categories, identity_check).
    """
    categories, identities = {}, {}
    for category, results_for_category in raw_results.items():
        categories[category], identities[category] = extract_category_with_identity(
            supplier_name, category, results_for_category, context
        )
    identity_check = combine_identity_checks(context, identities)
    save_extraction_result(supplier_name, categories, context, identity_check)
    return categories, identity_check
