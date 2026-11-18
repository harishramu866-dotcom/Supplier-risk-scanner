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


FULL_CONTEXT = {
    "country": "Taiwan",
    "city": "New Taipei City",
    "industry": "Electronics manufacturing",
    "website_domain": "foxconn.com",
    "parent_company": "Hon Hai Precision Industry",
}


def test_old_format_report_still_passes():
    # Saved before supplier_context / identity_check existed: neither key is present.
    report = make_report()
    assert "supplier_context" not in report and "identity_check" not in report
    validate_report(report)


def test_checked_in_reports_still_validate():
    # Every report already saved in reports/ (all written before the new fields) must still pass.
    from pathlib import Path
    import json

    paths = list((Path(__file__).resolve().parent.parent / "reports").glob("*.json"))
    assert paths
    for path in paths:
        validate_report(json.loads(path.read_text(encoding="utf-8")))


def test_report_with_context_and_identity_passes():
    report = make_report(
        supplier_context=FULL_CONTEXT,
        identity_check={"status": "Confirmed", "note": "Domain and parent company match."},
    )
    validate_report(report)


def test_partial_context_passes():
    validate_report(make_report(supplier_context={"country": "Vietnam"}))
    validate_report(make_report(supplier_context={}))


@pytest.mark.parametrize("status", ["Confirmed", "Ambiguous", "Unverified"])
def test_every_identity_status_passes(status):
    assert is_valid_report(make_report(identity_check={"status": status, "note": "Because."}))


def test_identity_check_without_context_passes():
    assert is_valid_report(make_report(identity_check={"status": "Unverified", "note": "No context."}))


def test_invalid_identity_status_fails():
    assert not is_valid_report(make_report(identity_check={"status": "Probably", "note": "Because."}))


def test_identity_check_missing_note_fails():
    assert not is_valid_report(make_report(identity_check={"status": "Confirmed"}))


def test_identity_check_missing_status_fails():
    assert not is_valid_report(make_report(identity_check={"note": "Because."}))


def test_identity_check_extra_field_fails():
    assert not is_valid_report(make_report(identity_check={"status": "Confirmed", "note": "x", "score": 1}))


def test_unknown_context_field_fails():
    assert not is_valid_report(make_report(supplier_context={"favorite_color": "blue"}))


def test_non_string_context_value_fails():
    assert not is_valid_report(make_report(supplier_context={"country": 44}))


def test_context_must_be_an_object():
    assert not is_valid_report(make_report(supplier_context="Taiwan"))
