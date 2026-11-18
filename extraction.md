# Stage 3 — extraction (the core AI step)

**Input:** supplier name + optional supplier context (country, city,
industry, website domain, parent company) + raw search results for one
category (title, snippet, URL per result)
**Output:** structured findings for that category, matching
`schemas/risk_report.schema.json`, plus an `identity_check` for the call.
The `identity_check` is not part of the category object: code strips it off,
combines the five categories' checks into the report-level `identity_check`,
and forces any category whose check is "Ambiguous" to Unknown with no findings.
**AI's job here:** read messy, unstructured text and decide what's an
actual claim worth recording, versus noise — this is the step where
getting the prompt right matters most

## Prompt

```
You are extracting compliance risk findings from web search results about
a supplier. Review the results below and determine the status of this
category for this supplier.

Supplier: {supplier_name}
{context_block}
Category: {category}  (one of: labor, environmental, sanctions, financial, legal)
Search results:
{raw results: title, snippet, url — one per result}

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
{
  "status": "Clear" | "Flagged" | "Unknown",
  "findings": [
    { "claim": "...", "source": "https://...", "confidence": "Low" | "Medium" | "High" }
  ],
  "identity_check": { "status": "Confirmed" | "Ambiguous" | "Unverified", "note": "..." }
}
```

## Notes for implementation

- Run this once per category (5 calls per supplier in v1), not once for
  all results combined — keeping categories separate is what makes the
  "Unknown" status honest per-category rather than blurred across the
  whole report
- The "verify relevance" instruction is doing a lot of work here — this is
  the step most likely to need iteration once you see real results.
  Wrong-company matches are the most common failure mode to watch for
