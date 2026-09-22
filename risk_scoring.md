# Stage 4 — risk scoring (plain code, NOT an AI call)

**Input:** the five category objects from stage 3 (already structured)
**Output:** `overall_risk` value for the report
**Why not AI:** once findings are structured, the decision is simple
enough to write as a rule. A fixed rule is deterministic (same input →
same output, every run) and free to compute, unlike another model call.

## Rule (pseudocode)

```
def compute_overall_risk(categories):
    statuses = [categories[c]["status"] for c in categories]

    if any(status == "Flagged" for status in statuses):
        # check severity: any High-confidence flagged finding → High risk
        for cat in categories.values():
            if cat["status"] == "Flagged":
                if any(f["confidence"] == "High" for f in cat["findings"]):
                    return "High"
        return "Medium"  # flagged, but only Low/Medium confidence findings

    if any(status == "Unknown" for status in statuses):
        return "Unknown"  # don't call it Low if you didn't actually check everything

    return "Low"  # all categories Clear
```

## Why this ordering

1. Any flagged finding takes priority over unknowns — a real problem you
   found matters more than a gap in coverage
2. Unknown beats Low — an unverified supplier should never look the same
   as a verified-clean one, even if nothing bad turned up
3. Low only when every category was actually checked and came back clean

This function has no AI call in it. If you're tempted to add one ("ask the
model to weigh the findings"), that's a sign the categories/confidence
levels from stage 3 aren't expressive enough yet — fix the schema, not
this function.
