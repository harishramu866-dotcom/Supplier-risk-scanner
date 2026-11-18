"""Stage 2: search agent (see search_agent.md).

Generates search queries per category via Claude, then runs each query
against the Brave Search API and collects raw results.
"""

import json
import os
import re
from datetime import datetime

import anthropic
import requests
from dotenv import load_dotenv

from risk_scanner.context import clean_context, format_context_block
from risk_scanner.json_utils import parse_json_object

load_dotenv()

CATEGORY_NAMES = ("labor", "environmental", "sanctions", "financial", "legal")

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

OUTPUT_DIR = "output"

QUERY_GENERATION_PROMPT = """You are researching a supplier for a compliance risk check. Given the
supplier name below, generate 2-3 targeted web search queries for EACH of
these five categories: labor, environmental, sanctions, financial, legal.

Supplier: {supplier_name}
{context_block}

Rules:
- Queries should be specific enough to surface real news, not generic
  company overviews (bad: "Acme Textiles news" — good: "Acme Textiles
  labor violation OR strike OR unsafe conditions")
- Include the supplier's likely parent company or alternate names if you
  can infer them, since red flags sometimes attach to the parent entity
- If a parent company is given in the context, search it directly in some of
  the queries for each category, in addition to the supplier itself
- If a country is given, use it where it helps tell similarly named
  companies apart. If a website domain is given, use it in a few queries per
  category, since the domain points at the right company — but not in every
  query
- Do NOT append the industry or the city to every query. News articles often
  leave them out, and a query that requires them hides real findings.
  Industry and city are for verifying results later, not blanket search terms
- For sanctions specifically, include a query checking against the
  supplier's country of operation (the supplied country if there is one),
  since sanctions lists are country-specific
- Do not invent facts about the supplier — you are only generating search
  queries, not answering yet

Output as JSON:
{{
  "labor": ["query 1", "query 2"],
  "environmental": ["query 1", "query 2"],
  "sanctions": ["query 1", "query 2"],
  "financial": ["query 1", "query 2"],
  "legal": ["query 1", "query 2"]
}}"""


def generate_search_queries(
    supplier_name: str,
    context: dict | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Stage 2 step 1: ask Claude what to search for. Returns {category: [queries]}."""
    client = client or anthropic.Anthropic()
    prompt = QUERY_GENERATION_PROMPT.format(
        supplier_name=supplier_name,
        context_block=format_context_block(context),
    )

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    queries = parse_json_object(text)

    missing = [name for name in CATEGORY_NAMES if name not in queries]
    if missing:
        raise ValueError(f"model output missing categories: {missing}\nraw output: {text}")

    return queries


def run_search(query: str, count: int = 5) -> list[dict]:
    """Stage 2 step 2: run one query against Brave Search, return raw title/snippet/url hits."""
    api_key = os.environ["BRAVE_API_KEY"]
    response = requests.get(
        BRAVE_SEARCH_URL,
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
        params={"q": query, "count": count},
        timeout=15,
    )
    response.raise_for_status()
    results = response.json().get("web", {}).get("results", [])
    return [
        {"title": r.get("title", ""), "snippet": r.get("description", ""), "url": r.get("url", "")}
        for r in results
    ]


def run_all_searches(queries_by_category: dict) -> dict:
    """Run every generated query, grouped by category, per query."""
    return {
        category: {query: run_search(query) for query in queries}
        for category, queries in queries_by_category.items()
    }


def save_scan_result(result: dict, output_dir: str = OUTPUT_DIR) -> str:
    """Save a stage 2 result to output/<supplier>_<timestamp>.json. Returns the path."""
    os.makedirs(output_dir, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", result["supplier_name"].lower()).strip("_")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"{slug}_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    return path


def build_scan_result(supplier_name: str, queries: dict, raw_results: dict, context: dict | None = None) -> dict:
    """The stage 2 output shape. supplier_context is included only when some context was given."""
    result = {"supplier_name": supplier_name}
    cleaned = clean_context(context)
    if cleaned:
        result["supplier_context"] = cleaned
    result.update(queries=queries, raw_results=raw_results)
    return result


def scan_supplier(supplier_name: str, context: dict | None = None) -> dict:
    """Full stage 2: generate queries, run them all, save the result to output/, and return it."""
    queries = generate_search_queries(supplier_name, context)
    raw_results = run_all_searches(queries)
    result = build_scan_result(supplier_name, queries, raw_results, context)
    result["saved_to"] = save_scan_result(result)
    return result
