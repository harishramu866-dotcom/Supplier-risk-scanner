# Stage 3 — extraction (the core AI step)

**Input:** supplier name + raw search results for one category (title,
snippet, URL per result)
**Output:** structured findings for that category, matching
`schemas/risk_report.schema.json`
**AI's job here:** read messy, unstructured text and decide what's an
actual claim worth recording, versus noise — this is the step where
getting the prompt right matters most

## Prompt

```
You are extracting compliance risk findings from web search results about
a supplier. Review the results below and determine the status of this
category for this supplier.

Supplier: {supplier_name}
Category: {category}  (one of: labor, environmental, sanctions, financial, legal)
Search results:
{raw results: title, snippet, url — one per result}

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
{
  "status": "Clear" | "Flagged" | "Unknown",
  "findings": [
    { "claim": "...", "source": "https://...", "confidence": "Low" | "Medium" | "High" }
  ]
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
