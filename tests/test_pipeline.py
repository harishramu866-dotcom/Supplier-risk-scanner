import json
import sys
from pathlib import Path

import pytest

import scripts.run_iterative_scan as cli
from risk_scanner import pipeline
from risk_scanner import report as report_module
from risk_scanner.validation import validate_report

CATEGORIES = {
    name: {"status": "Clear", "findings": []}
    for name in ("labor", "environmental", "sanctions", "financial", "legal")
}
IDENTITY = {"status": "Confirmed", "note": "Domain matches."}
SUMMARY = {"summary": "Nothing found.", "data_completeness_note": "All five categories were checked."}


def fake_iterative_scan(name, context, log=print):
    log("round 0")
    return {
        "supplier_name": name,
        "supplier_context": {"country": "India"},
        "identity_check": IDENTITY,
        "categories": CATEGORIES,
    }


def test_run_scan_saves_a_valid_report_and_logs_every_step(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "iterative_scan", fake_iterative_scan)
    monkeypatch.setattr(report_module, "generate_summary", lambda *args, **kwargs: SUMMARY)
    lines = []

    report, path = pipeline.run_scan("Acme", {"country": "India"}, log=lines.append)

    assert Path(path).parent.name == "reports" and Path(path).exists()
    assert json.loads(Path(path).read_text(encoding="utf-8")) == report
    validate_report(report)
    assert report["supplier_context"] == {"country": "India"}
    assert report["identity_check"] == IDENTITY
    assert lines[0] == "round 0"
    assert any(line.startswith("Saved report to") for line in lines)


def test_a_scan_that_fails_before_the_report_is_valid_saves_no_report(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "iterative_scan", fake_iterative_scan)

    def broken_summary(*args, **kwargs):
        raise ValueError("model returned something unusable")

    monkeypatch.setattr(report_module, "generate_summary", broken_summary)
    with pytest.raises(ValueError):
        pipeline.run_scan("Acme", None, log=lambda line: None)
    assert not (tmp_path / "reports").exists()


def test_the_command_line_calls_the_same_function_as_the_dashboard(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "run_scan", lambda name, context: calls.append((name, context)))
    monkeypatch.setattr(sys, "argv", ["run_iterative_scan", "Acme", "--country", "India", "--domain", "acme.in"])
    cli.main()
    assert calls == [("Acme", {"country": "India", "website_domain": "acme.in"})]
