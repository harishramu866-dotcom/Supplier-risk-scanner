"""Renders the real dashboard headlessly. The scan itself is always replaced with a fake: no live APIs."""

import threading
import time
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parent.parent / "app.py"

REPORT = {
    "supplier_name": "Acme Textiles",
    "search_date": "2026-11-18",
    "overall_risk": "High",
    "summary": "Acme has a serious labor finding.",
    "data_completeness_note": "All five categories were checked.",
    "categories": {
        name: {"status": "Clear", "findings": []}
        for name in ("labor", "environmental", "sanctions", "financial", "legal")
    },
}


@pytest.fixture(autouse=True)
def fresh_runner():
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def open_app() -> AppTest:
    at = AppTest.from_file(str(APP), default_timeout=30).run()
    assert not at.exception
    return at


def button(at: AppTest, label: str):
    return next(b for b in at.button if b.label == label)


def run_until(at: AppTest, done, attempts: int = 25) -> AppTest:
    """The page polls once a second in a browser; here we rerun by hand until `done(at)` is true."""
    for _ in range(attempts):
        if done(at):
            return at
        time.sleep(0.1)
        at.run()
        assert not at.exception
    raise AssertionError("the page never reached the expected state")


def test_there_are_exactly_two_tabs():
    assert [tab.label for tab in open_app().tabs] == ["Supplier Reports", "New Scan"]


def test_the_csv_feature_is_gone():
    at = open_app()
    assert len(at.get("file_uploader")) == 0
    source = APP.read_text(encoding="utf-8").lower()
    for leftover in ("csv", "performance", "pandas"):
        assert leftover not in source


def test_the_form_has_the_expected_fields_and_the_cost_note():
    at = open_app()
    assert sorted(t.label for t in at.text_input) == sorted(
        ["Supplier name (required)", "Country", "City", "Industry", "Website domain", "Parent company"]
    )
    assert button(at, "Run scan").disabled is False
    assert any("Each scan uses paid API calls." in c.value for c in at.caption)


def test_an_empty_name_shows_a_message_and_runs_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr("risk_scanner.pipeline.run_scan", lambda *args, **kwargs: calls.append(args))
    at = open_app()
    at.text_input(key="scan_name").input("   ")
    button(at, "Run scan").click().run()
    time.sleep(0.3)
    assert any("supplier name" in e.value.lower() for e in at.error)
    assert calls == []


def test_a_scan_runs_with_the_form_values_and_shows_the_finished_report(monkeypatch):
    calls = []

    def fake_scan(name, context, log=print):
        calls.append((name, context))
        log("=== Round 0 ===")
        return REPORT, "reports/acme_textiles_report_20261118_100000.json"

    monkeypatch.setattr("risk_scanner.pipeline.run_scan", fake_scan)
    at = open_app()
    at.text_input(key="scan_name").input("Acme Textiles")
    at.text_input(key="scan_country").input("Vietnam")
    at.text_input(key="scan_domain").input("https://www.acme.vn/")
    button(at, "Run scan").click().run()

    run_until(at, lambda a: len(a.success) > 0)
    assert calls == [("Acme Textiles", {"country": "Vietnam", "website_domain": "acme.vn"})]
    assert "acme_textiles_report_20261118_100000.json" in at.success[0].value
    shown = " ".join(m.value for m in at.markdown)
    assert "Acme has a serious labor finding." in shown
    assert "High" in shown
    assert any(b.label == "Open full report" for b in at.button)
    assert button(at, "Run scan").disabled is False


def test_run_scan_is_disabled_while_a_scan_is_running(monkeypatch):
    release = threading.Event()
    calls = []

    def slow_scan(name, context, log=print):
        calls.append(name)
        log("=== Round 0 ===")
        release.wait(10)
        return REPORT, "reports/x.json"

    monkeypatch.setattr("risk_scanner.pipeline.run_scan", slow_scan)
    try:
        at = open_app()
        at.text_input(key="scan_name").input("Acme Textiles")
        button(at, "Run scan").click().run()

        assert button(at, "Run scan").disabled is True
        assert all(t.disabled for t in at.text_input)
        assert any("Round 0" in c.value for c in at.code)
        assert calls == ["Acme Textiles"]
    finally:
        release.set()


def test_a_failed_scan_shows_a_plain_message_and_the_trace(monkeypatch):
    def failing_scan(name, context, log=print):
        log("=== Round 0 ===")
        raise RuntimeError("Traceback: secret detail")

    monkeypatch.setattr("risk_scanner.pipeline.run_scan", failing_scan)
    at = open_app()
    at.text_input(key="scan_name").input("Acme Textiles")
    button(at, "Run scan").click().run()

    run_until(at, lambda a: len(a.error) > 0)
    assert "Something went wrong (RuntimeError)" in at.error[0].value
    assert "secret detail" not in at.error[0].value
    assert any("Round 0" in c.value for c in at.code)
    assert not any(b.label == "Open full report" for b in at.button)
