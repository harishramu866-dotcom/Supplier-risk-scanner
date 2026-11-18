"""Iterative search loop: retry categories that came back Unknown with new queries.

Round 0 is the normal one-shot search + extraction. Each later round
generates 1-2 new queries for every category still Unknown, searches,
and re-runs extraction on all of that category's results so far. Stops
when nothing is Unknown, when a round makes no progress, or after
MAX_EXTRA_ROUNDS extra rounds.
"""

import anthropic
from dotenv import load_dotenv

from risk_scanner.context import clean_context, format_context_block
from risk_scanner.extraction import extract_category_with_identity, save_extraction_result
from risk_scanner.identity import combine_identity_checks
from risk_scanner.json_utils import parse_json_object
from risk_scanner.search_agent import build_scan_result, generate_search_queries, run_search, save_scan_result

load_dotenv()

MAX_EXTRA_ROUNDS = 2

FOLLOWUP_PROMPT = """You are researching a supplier for a compliance risk check. A first round of web
searches for the category below did not turn up usable results, so this category is still unverified.

Supplier: {supplier_name}
{context_block}
Category: {category}

Queries already tried (do not repeat them):
{tried}

Generate 1-2 NEW targeted web search queries for this category only. Try a different angle than
before, for example: the parent company or a subsidiary name, an alternate spelling or
transliteration of the supplier name, a local-language or country-specific name, or a more specific
angle such as a named regulator, court, or list relevant to {category}.

Rules:
- Do not invent facts about the supplier — you are only generating search queries.
- Each query must differ meaningfully from those already tried.
- Use the context, if any, to pick the angle (parent company, website domain, country), but do
  NOT append the industry or city to every query; news articles often omit them.

Output as JSON:
{{ "queries": ["query 1", "query 2"] }}"""


def generate_followup_queries(
    supplier_name: str,
    category: str,
    tried_queries: list[str],
    context: dict | None = None,
    client: anthropic.Anthropic | None = None,
) -> list[str]:
    client = client or anthropic.Anthropic()
    prompt = FOLLOWUP_PROMPT.format(
        supplier_name=supplier_name,
        context_block=format_context_block(context),
        category=category,
        tried="\n".join(f"- {q}" for q in tried_queries),
    )
    response = client.messages.create(
        model="claude-opus-5",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(block.text for block in response.content if block.type == "text")
    tried_lower = {q.lower() for q in tried_queries}
    new_queries = [q for q in parse_json_object(text).get("queries", []) if q.lower() not in tried_lower]
    return new_queries[:2]


def iterative_scan(
    supplier_name: str,
    context: dict | None = None,
    max_extra_rounds: int = MAX_EXTRA_ROUNDS,
    log=print,
) -> dict:
    context = clean_context(context)
    log(f"=== Round 0: initial search + extraction for {supplier_name} ===")
    log(format_context_block(context))
    queries = generate_search_queries(supplier_name, context)
    raw_results: dict[str, dict[str, list]] = {}
    for category, category_queries in queries.items():
        raw_results[category] = {q: run_search(q) for q in category_queries}
        total = sum(len(hits) for hits in raw_results[category].values())
        log(f"[round 0] {category}: ran {len(category_queries)} queries, {total} results")

    categories: dict[str, dict] = {}
    identities: dict[str, dict] = {}
    for category, results in raw_results.items():
        categories[category], identities[category] = extract_category_with_identity(
            supplier_name, category, results, context
        )
        log(
            f"[round 0] {category}: {categories[category]['status']} "
            f"({len(categories[category]['findings'])} findings), identity {identities[category]['status']}"
        )

    stop_reason = f"reached the cap of {max_extra_rounds} extra rounds"
    for round_num in range(1, max_extra_rounds + 1):
        unknown = [c for c, result in categories.items() if result["status"] == "Unknown"]
        if not unknown:
            stop_reason = "no categories are Unknown"
            break

        log(f"\n=== Round {round_num}: retrying Unknown categories: {', '.join(unknown)} ===")
        progressed = False
        for category in unknown:
            tried = list(raw_results[category])
            new_queries = generate_followup_queries(supplier_name, category, tried, context)
            if not new_queries:
                log(f"[round {round_num}] {category}: model produced no new queries; leaving Unknown")
                continue
            log(f"[round {round_num}] {category}: Unknown. Trying {len(new_queries)} new quer{'y' if len(new_queries) == 1 else 'ies'}:")

            seen_urls = {hit["url"] for hits in raw_results[category].values() for hit in hits}
            found_new = False
            for query in new_queries:
                hits = run_search(query)
                raw_results[category][query] = hits
                queries[category].append(query)
                fresh = [h for h in hits if h["url"] not in seen_urls]
                seen_urls.update(h["url"] for h in hits)
                found_new = found_new or bool(fresh)
                log(f"    {query}\n      -> {len(hits)} results, {len(fresh)} not seen before")

            if not found_new:
                log(f"[round {round_num}] {category}: no new results; leaving Unknown")
                continue

            categories[category], identities[category] = extract_category_with_identity(
                supplier_name, category, raw_results[category], context
            )
            result = categories[category]
            log(
                f"[round {round_num}] {category}: re-extracted on all results -> {result['status']} "
                f"({len(result['findings'])} findings), identity {identities[category]['status']}"
            )
            if result["status"] != "Unknown":
                progressed = True

        if not progressed:
            stop_reason = f"round {round_num} made no progress on the categories it retried"
            break

    still_unknown = [c for c, result in categories.items() if result["status"] == "Unknown"]
    log(f"\n=== Done: stopped because {stop_reason}. Still Unknown: {', '.join(still_unknown) or 'none'} ===")

    identity_check = combine_identity_checks(context, identities)
    log(f"Identity check: {identity_check['status']} - {identity_check['note']}")

    scan_result = build_scan_result(supplier_name, queries, raw_results, context)
    scan_path = save_scan_result(scan_result)
    extraction_path = save_extraction_result(supplier_name, categories, context, identity_check)
    log(f"Saved stage 2 output to {scan_path}")
    log(f"Saved stage 3 output to {extraction_path}")

    return {**scan_result, "identity_check": identity_check, "categories": categories}
