# Stage 2 — search agent

**Input:** supplier name (string, required), plus optional context: country,
city, industry, website domain, parent company
**Output:** a list of search queries to run, grouped by category
**AI's job here:** decide *what* to search for — not a fixed template, but
judgment about what's likely to surface real findings for this supplier

## Prompt

```
You are researching a supplier for a compliance risk check. Given the
supplier name below, generate 2-3 targeted web search queries for EACH of
these five categories: labor, environmental, sanctions, financial, legal.

Supplier: {supplier_name}
{context_block}   (e.g. "Context supplied by the user (treat as true):
                   - Country: ..." — or "Context: none supplied.")

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
