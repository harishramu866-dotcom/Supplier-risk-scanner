from risk_scanner.scoring import compute_overall_risk


def clear(name):
    return {"status": "Clear", "findings": []}


def unknown(name):
    return {"status": "Unknown", "findings": []}


def flagged(confidence):
    return {
        "status": "Flagged",
        "findings": [
            {"claim": "some claim", "source": "https://example.com", "confidence": confidence}
        ],
    }


def test_all_clear_is_low():
    categories = {name: clear(name) for name in ("labor", "environmental", "sanctions", "financial", "legal")}
    assert compute_overall_risk(categories) == "Low"


def test_unknown_category_beats_low():
    categories = {
        "labor": clear("labor"),
        "environmental": unknown("environmental"),
        "sanctions": clear("sanctions"),
        "financial": clear("financial"),
        "legal": clear("legal"),
    }
    assert compute_overall_risk(categories) == "Unknown"


def test_flagged_with_high_confidence_finding_is_high():
    categories = {
        "labor": flagged("High"),
        "environmental": clear("environmental"),
        "sanctions": clear("sanctions"),
        "financial": clear("financial"),
        "legal": clear("legal"),
    }
    assert compute_overall_risk(categories) == "High"


def test_flagged_with_only_low_medium_confidence_is_medium():
    categories = {
        "labor": flagged("Medium"),
        "environmental": clear("environmental"),
        "sanctions": clear("sanctions"),
        "financial": clear("financial"),
        "legal": clear("legal"),
    }
    assert compute_overall_risk(categories) == "Medium"


def test_flagged_takes_priority_over_unknown():
    categories = {
        "labor": flagged("High"),
        "environmental": unknown("environmental"),
        "sanctions": clear("sanctions"),
        "financial": clear("financial"),
        "legal": clear("legal"),
    }
    assert compute_overall_risk(categories) == "High"
