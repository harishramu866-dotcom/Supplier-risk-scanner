"""Stage 2: search agent (see search_agent.md).

Generates search queries per category via Claude, then runs each query
against the Brave Search API and collects raw results.
"""

import json
import os

import anthropic
import requests
from dotenv import load_dotenv

load_dotenv()

CATEGORY_NAMES = ("labor", "environmental", "sanctions", "financial", "legal")

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

QUERY_GENERATION_PROMPT = """You are researching a supplier for a compliance risk check. Given the
supplier name below, generate 2-3 targeted web search queries for EACH of
these five categories: labor, environmental, sanctions, financial, legal.

Supplier: {supplier_name}
{context_line}

Rules:
- Queries should be specific enough to surface real news, not generic
  company overviews (bad: "Acme Textiles news" — good: "Acme Textiles
  labor violation OR strike OR unsafe conditions")
- Include the supplier's likely parent company or alternate names if you
  can infer them, since red flags sometimes attach to the parent entity
- For sanctions specifically, include a query checking against the
  supplier's country of operation, since sanctions lists are
  country-specific
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
    context: str | None = None,
    client: anthropic.Anthropic | None = None,
) -> dict:
    """Stage 2 step 1: ask Claude what to search for. Returns {category: [queries]}."""
    client = client or anthropic.Anthropic()
    context_line = f"Context: {context}" if context else ""
    prompt = QUERY_GENERATION_PROMPT.format(supplier_name=supplier_name, context_line=context_line)

    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(block.text for block in response.content if block.type == "text")
    queries = _parse_json_object(text)

    missing = [name for name in CATEGORY_NAMES if name not in queries]
    if missing:
        raise ValueError(f"model output missing categories: {missing}\nraw output: {text}")

    return queries


def _parse_json_object(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


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


def scan_supplier(supplier_name: str, context: str | None = None) -> dict:
    """Full stage 2: generate queries, run them all, return queries + raw results."""
    queries = generate_search_queries(supplier_name, context)
    raw_results = run_all_searches(queries)
    return {"supplier_name": supplier_name, "queries": queries, "raw_results": raw_results}
