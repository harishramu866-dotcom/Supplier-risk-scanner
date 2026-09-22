# Stage 2 — search agent

**Input:** supplier name (string), optionally country/industry for context
**Output:** a list of search queries to run, grouped by category
**AI's job here:** decide *what* to search for — not a fixed template, but
judgment about what's likely to surface real findings for this supplier

## Prompt

```
You are researching a supplier for a compliance risk check. Given the
supplier name below, generate 2-3 targeted web search queries for EACH of
these five categories: labor, environmental, sanctions, financial, legal.

Supplier: {supplier_name}
{optional context: country, industry}

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
{
  "labor": ["query 1", "query 2"],
  "environmental": ["query 1", "query 2"],
  "sanctions": ["query 1", "query 2"],
  "financial": ["query 1", "query 2"],
  "legal": ["query 1", "query 2"]
}
```

## Notes for implementation

- Run every query returned, collect raw results (title, snippet, URL) per
  category — this raw bundle is what stage 3 (extraction) reads
- v1 runs this once, fixed. In v2 this becomes a loop (see the project doc,
  "+ Iterative search") — same prompt shape, but called again with a note
  on what's missing so far
