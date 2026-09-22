# Supplier risk scanner — v1 (MVP)

Given a supplier name, produce a structured risk report covering labor,
environmental, sanctions, financial, and legal red flags, sourced from
public web search.

## Pipeline (v1 scope)

```
supplier name → search agent → extraction → risk scoring → risk report (JSON) → dashboard
```

v1 is intentionally simple: **one-shot** search (fixed number of queries,
no looping), **single-pass** extraction, and **rule-based** scoring (plain
code, no AI). See `/logic/risk_scoring.md` for why scoring is not a prompt.

## Folder structure

```
supplier-risk-scanner/
├── README.md
├── schemas/
│   └── risk_report.schema.json   — the JSON shape every scan produces
├── prompts/
│   ├── search_agent.md           — stage 2: what queries to run
│   ├── extraction.md             — stage 3: turn results into structured findings
│   └── report_summary.md         — stage 5: write the plain-English summary
└── logic/
    └── risk_scoring.md           — stage 4: the scoring rule (plain code, not a prompt)
```

## Where AI is used (v1)

| Stage | AI? |
| --- | --- |
| Search agent | Yes — `prompts/search_agent.md` |
| Extraction | Yes — `prompts/extraction.md` (the core AI step) |
| Risk scoring | No — `logic/risk_scoring.md` is plain if/else |
| Report summary | Yes — `prompts/report_summary.md` |
| Dashboard | No — renders the JSON, no reasoning |

## Suggested build order in Claude Code

1. Get `schemas/risk_report.schema.json` finalized — everything else targets this shape.
2. Wire up the search step using `prompts/search_agent.md` — test it standalone, print raw results.
3. Wire up extraction using `prompts/extraction.md` — feed it the search results, check the output validates against the schema.
4. Implement `logic/risk_scoring.md` as plain code — no AI call.
5. Wire up `prompts/report_summary.md` last — it's the easiest since by then you have clean structured data to summarize.
6. Dashboard reads the JSON reports from disk — no new logic, just display.

Test each stage in isolation before chaining them — much easier to debug a bad
extraction than a bad end-to-end run.
