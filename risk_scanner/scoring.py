"""Stage 4: rule-based overall risk scoring (see logic/risk_scoring.md)."""

CATEGORY_NAMES = ("labor", "environmental", "sanctions", "financial", "legal")


def compute_overall_risk(categories: dict) -> str:
    statuses = [categories[name]["status"] for name in categories]

    if any(status == "Flagged" for status in statuses):
        for category in categories.values():
            if category["status"] == "Flagged":
                if any(finding["confidence"] == "High" for finding in category["findings"]):
                    return "High"
        return "Medium"

    if any(status == "Unknown" for status in statuses):
        return "Unknown"

    return "Low"
