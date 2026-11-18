"""Optional supplier context (country, city, industry, domain, parent) used to disambiguate similar names."""

import re

CONTEXT_FIELDS = ("country", "city", "industry", "website_domain", "parent_company")

CONTEXT_LABELS = {
    "country": "Country",
    "city": "City",
    "industry": "Industry",
    "website_domain": "Website domain",
    "parent_company": "Parent company",
}


def normalize_domain(value: str) -> str:
    """'https://www.Example.com/about?x=1' -> 'example.com'."""
    value = re.sub(r"^[a-z][a-z0-9+.-]*://", "", value.strip().lower())
    value = re.split(r"[/?#]", value, maxsplit=1)[0]
    return value.removeprefix("www.")


def clean_context(context: dict | None) -> dict:
    """Keep only known fields that have a non-blank string value."""
    cleaned = {}
    for field in CONTEXT_FIELDS:
        value = (context or {}).get(field)
        if isinstance(value, str) and value.strip():
            cleaned[field] = normalize_domain(value) if field == "website_domain" else value.strip()
    return {field: value for field, value in cleaned.items() if value}


def format_context_block(context: dict | None) -> str:
    cleaned = clean_context(context)
    if not cleaned:
        return "Context: none supplied."
    lines = ["Context supplied by the user (treat as true):"]
    lines += [f"- {CONTEXT_LABELS[field]}: {value}" for field, value in cleaned.items()]
    return "\n".join(lines)


def add_context_arguments(parser) -> None:
    """Add the optional context flags to an argparse parser."""
    parser.add_argument("--country", help="country the supplier operates in")
    parser.add_argument("--city", help="city the supplier is based in")
    parser.add_argument("--industry", help="the supplier's industry")
    parser.add_argument("--domain", dest="website_domain", help="supplier website domain, e.g. example.com")
    parser.add_argument("--parent", dest="parent_company", help="parent company, if known")


def context_from_args(args) -> dict:
    return clean_context({field: getattr(args, field, None) for field in CONTEXT_FIELDS})
