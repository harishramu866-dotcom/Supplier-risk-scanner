import pytest
from jsonschema import ValidationError

from risk_scanner.validation import is_valid_report, validate_report


def make_report(**overrides):
    report = {
        "supplier_name": "Acme Corp",
        "search_date": "2026-09-22",
        "overall_risk": "Low",
        "categories": {
            name: {"status": "Clear", "findings": []}
            for name in ("labor", "environmental", "sanctions", "financial", "legal")
        },
        "summary": "No issues found.",
        "data_completeness_note": "All categories checked.",
    }
    report.update(overrides)
    return report


def test_valid_report_passes():
    validate_report(make_report())
    assert is_valid_report(make_report())


def test_missing_required_field_fails():
    report = make_report()
    del report["summary"]
    with pytest.raises(ValidationError):
        validate_report(report)
    assert not is_valid_report(report)


def test_invalid_enum_value_fails():
    report = make_report(overall_risk="Extreme")
    assert not is_valid_report(report)


def test_missing_category_fails():
    report = make_report()
    del report["categories"]["legal"]
    assert not is_valid_report(report)


def test_finding_missing_confidence_fails():
    report = make_report()
    report["categories"]["labor"] = {
        "status": "Flagged",
        "findings": [{"claim": "underpaid workers", "source": "https://example.com/news"}],
    }
    assert not is_valid_report(report)
