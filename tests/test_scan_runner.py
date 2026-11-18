import json
import threading
from types import SimpleNamespace

import anthropic
import httpx2
import pytest
import requests
from jsonschema import ValidationError

from risk_scanner.scan_runner import ScanRunner, describe_error, redact_secrets

REPORT = {"supplier_name": "Acme", "overall_risk": "Low"}
REQUEST = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def api_error(cls, status):
    return cls("SECRETMSG", response=httpx2.Response(status, request=REQUEST), body=None)


def test_runs_the_scan_with_the_name_and_context_and_keeps_the_trace():
    seen = {}

    def scan(name, context, log):
        seen.update(name=name, context=context)
        log("round 0")
        log("round 1")
        return REPORT, "reports/acme.json"

    runner = ScanRunner(scan)
    job = runner.start("Acme", {"country": "India"})
    assert job.wait(5)
    assert (job.status, job.report, job.report_path, job.error) == ("done", REPORT, "reports/acme.json", None)
    assert job.lines() == ["round 0", "round 1"]
    assert seen == {"name": "Acme", "context": {"country": "India"}}
    assert not runner.is_running()


def test_a_second_scan_cannot_start_while_one_is_running():
    release = threading.Event()
    calls = []

    def scan(name, context, log):
        calls.append(name)
        release.wait(5)
        return REPORT, "p"

    runner = ScanRunner(scan)
    first = runner.start("Acme")
    assert runner.is_running()
    assert runner.start("Acme") is None
    assert runner.start("Other") is None

    release.set()
    assert first.wait(5)
    assert calls == ["Acme"]
    assert runner.start("Third") is not None


def test_a_failed_scan_keeps_the_trace_gives_a_plain_error_and_no_report():
    def scan(name, context, log):
        log("round 0")
        raise ValueError('raw detail: {"oops"')

    runner = ScanRunner(scan)
    job = runner.start("Acme")
    assert job.wait(5)
    assert job.status == "error"
    assert job.report is None and job.report_path is None
    assert job.lines() == ["round 0"]
    assert "couldn't use" in job.error
    assert "raw detail" not in job.error
    assert not runner.is_running()


def test_an_unexpected_error_names_its_type_but_not_its_message():
    def scan(name, context, log):
        raise RuntimeError("secret detail")

    job = ScanRunner(scan).start("Acme")
    assert job.wait(5)
    assert "RuntimeError" in job.error and "secret detail" not in job.error


def test_api_keys_never_appear_in_the_trace_or_the_error(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-12345")
    monkeypatch.setenv("BRAVE_API_KEY", "BSA-brave-key-67890")

    def scan(name, context, log):
        log("calling with sk-ant-test-key-12345 and BSA-brave-key-67890")
        raise RuntimeError("bad key BSA-brave-key-67890")

    job = ScanRunner(scan).start("Acme")
    assert job.wait(5)
    shown = "\n".join(job.lines()) + job.error
    assert "sk-ant-test-key-12345" not in shown and "BSA-brave-key-67890" not in shown
    assert "[hidden]" in job.lines()[0]


def test_redact_secrets_ignores_unset_and_trivial_values(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("BRAVE_API_KEY", "x")
    assert redact_secrets("an x in the text") == "an x in the text"


@pytest.mark.parametrize(
    "exc, expected",
    [
        (api_error(anthropic.AuthenticationError, 401), "ANTHROPIC_API_KEY"),
        (api_error(anthropic.PermissionDeniedError, 403), "ANTHROPIC_API_KEY"),
        (api_error(anthropic.RateLimitError, 429), "rate limiting"),
        (api_error(anthropic.BadRequestError, 400), "credit balance"),
        (api_error(anthropic.InternalServerError, 500), "returned an error"),
        (anthropic.APIConnectionError(request=REQUEST), "Could not reach the Anthropic API"),
        (anthropic.APITimeoutError(request=REQUEST), "Could not reach the Anthropic API"),
        (requests.HTTPError(response=SimpleNamespace(status_code=401)), "BRAVE_API_KEY"),
        (requests.HTTPError(response=SimpleNamespace(status_code=429)), "rate limiting"),
        (requests.HTTPError(response=SimpleNamespace(status_code=500)), "returned an error"),
        (requests.ConnectionError("SECRETMSG"), "Could not reach Brave Search"),
        (requests.Timeout("SECRETMSG"), "Could not reach Brave Search"),
        (KeyError("BRAVE_API_KEY"), "BRAVE_API_KEY is missing"),
        (KeyError("ANTHROPIC_API_KEY"), "ANTHROPIC_API_KEY is missing"),
        (TypeError("Could not resolve authentication method SECRETMSG"), "ANTHROPIC_API_KEY is missing"),
        (ValueError("SECRETMSG"), "couldn't use"),
        (json.JSONDecodeError("SECRETMSG", "doc", 0), "couldn't use"),
        (ValidationError("SECRETMSG"), "couldn't use"),
        (KeyError("something_else"), "Something went wrong (KeyError)"),
    ],
)
def test_describe_error_is_plain_language_and_never_echoes_the_exception_text(exc, expected):
    message = describe_error(exc)
    assert expected in message
    assert "SECRETMSG" not in message
