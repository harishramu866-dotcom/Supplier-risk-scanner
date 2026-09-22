# Stage 5 — report summary

**Input:** the completed report (all five categories + overall_risk,
already computed)
**Output:** `summary` and `data_completeness_note` fields
**AI's job here:** turn structured data into something a human reads in
five seconds — this is a writing task, not a research task, since all the
facts are already gathered

## Prompt

```
Write a short risk summary for this supplier, based only on the
structured findings below. Do not add any new claims — only summarize
what's already here.

Supplier: {supplier_name}
Overall risk: {overall_risk}
Categories: {full categories object from stages 3-4}

Write two things:

1. summary: one paragraph (3-4 sentences) a compliance reviewer could read
   in five seconds. Lead with the most serious finding if there is one.
   Mention which categories were clear. Plain language, no jargon.

2. data_completeness_note: one sentence flagging any category marked
   "Unknown" and what that means for how much to trust this report. If
   nothing is Unknown, state that all five categories were checked.

Output as JSON:
{ "summary": "...", "data_completeness_note": "..." }
```

## Notes for implementation

- This call should never see raw search results — only the already-clean
  structured findings — which is what keeps it a writing task instead of
  a research task, and keeps it fast/cheap
- If `data_completeness_note` starts feeling like it's doing more than one
  sentence's worth of work, that's a sign too many categories are landing
  as "Unknown" — worth revisiting the search queries in
  `prompts/search_agent.md` before blaming this step
