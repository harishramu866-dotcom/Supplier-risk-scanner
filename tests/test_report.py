import json

from risk_scanner import report as report_module
from risk_scanner.report import assemble_report, generate_summary, save_report
from risk_scanner.validation import validate_report

CATEGORIES = {
    name: {"status": "Clear", "findings": []}
    for name in ("labor", "environmental", "sanctions", "financial", "legal")
}
SUMMARY = {"summary": "Nothing found.", "data_completeness_note": "All five categories were checked."}
CONTEXT = {"country": "Taiwan", "website_domain": "foxconn.com"}
AMBIGUOUS = {"status": "Ambiguous", "note": "Two companies share this name."}


def test_summary_prompt_includes_the_identity_check_when_given(fake_client):
    client = fake_client(SUMMARY)
    generate_summary("Acme", "Low", CATEGORIES, AMBIGUOUS, client)
    prompt = " ".join(client.prompts[0].split())
    assert "Identity check: Ambiguous - Two companies share this name." in prompt
    assert "status is Ambiguous or Unverified, add one more sentence" in prompt


def test_summary_prompt_omits_the_identity_check_for_older_reports(fake_client):
    client = fake_client(SUMMARY)
    generate_summary("Acme", "Low", CATEGORIES, None, client)
    assert "Identity check:" not in client.prompts[0]


def test_assemble_report_adds_context_and_identity(monkeypatch):
    seen = {}

    def fake_summary(supplier_name, overall_risk, categories, identity_check=None):
        seen["identity_check"] = identity_check
        return SUMMARY

    monkeypatch.setattr(report_module, "generate_summary", fake_summary)
    report = assemble_report("Acme", CATEGORIES, CONTEXT, AMBIGUOUS)

    assert report["supplier_context"] == CONTEXT
    assert report["identity_check"] == AMBIGUOUS
    assert seen["identity_check"] == AMBIGUOUS
    validate_report(report)


def test_assemble_report_without_context_or_identity_matches_the_old_format(monkeypatch):
    monkeypatch.setattr(report_module, "generate_summary", lambda *args, **kwargs: SUMMARY)
    report = assemble_report("Acme", CATEGORIES)
    assert "supplier_context" not in report and "identity_check" not in report
    validate_report(report)


def test_identity_check_does_not_change_the_score(monkeypatch):
    monkeypatch.setattr(report_module, "generate_summary", lambda *args, **kwargs: SUMMARY)
    plain = assemble_report("Acme", CATEGORIES)
    ambiguous = assemble_report("Acme", CATEGORIES, CONTEXT, AMBIGUOUS)
    assert plain["overall_risk"] == ambiguous["overall_risk"] == "Low"


def test_save_report_round_trips(monkeypatch, tmp_path):
    monkeypatch.setattr(report_module, "generate_summary", lambda *args, **kwargs: SUMMARY)
    report = assemble_report("Acme", CATEGORIES, CONTEXT, AMBIGUOUS)
    path = save_report(report, output_dir=str(tmp_path))
    assert json.loads(open(path, encoding="utf-8").read()) == report
