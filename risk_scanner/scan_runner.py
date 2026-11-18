"""Runs one scan at a time on a background thread, for a UI that shows live progress.

Every scan costs money, so starting a second one while one is running is refused here
rather than left to the UI. The thread keeps going if the page reruns or reloads.
"""

import os
import threading
import time
import uuid

import anthropic
import requests
from jsonschema import ValidationError

from risk_scanner import pipeline

SECRET_ENV_VARS = ("ANTHROPIC_API_KEY", "BRAVE_API_KEY")


def redact_secrets(text: str) -> str:
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name)
        if value and len(value) >= 8:
            text = text.replace(value, "[hidden]")
    return text


def describe_error(exc: Exception) -> str:
    """A plain-language message for a failed scan. Never includes the exception text, which can echo request details."""
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return "The Anthropic API rejected the request. Check ANTHROPIC_API_KEY in your .env file."
    if isinstance(exc, anthropic.RateLimitError):
        return "The Anthropic API is rate limiting requests. Wait a minute and try again."
    if isinstance(exc, anthropic.APIConnectionError):
        return "Could not reach the Anthropic API. Check your internet connection and try again."
    if isinstance(exc, anthropic.BadRequestError):
        return "The Anthropic API rejected the request. If this keeps happening, check your account's credit balance."
    if isinstance(exc, anthropic.APIStatusError):
        return "The Anthropic API returned an error. Try again in a few minutes."
    if isinstance(exc, requests.HTTPError):
        status = getattr(exc.response, "status_code", None)
        if status in (401, 403):
            return "Brave Search rejected the request. Check BRAVE_API_KEY in your .env file."
        if status == 429:
            return "Brave Search is rate limiting requests, or the monthly quota is used up. Try again later."
        return "Brave Search returned an error. Try again in a few minutes."
    if isinstance(exc, requests.RequestException):
        return "Could not reach Brave Search. Check your internet connection and try again."
    if isinstance(exc, KeyError) and exc.args and exc.args[0] in SECRET_ENV_VARS:
        return f"{exc.args[0]} is missing. Add it to your .env file."
    if isinstance(exc, TypeError) and "authentication" in str(exc).lower():
        return "ANTHROPIC_API_KEY is missing. Add it to your .env file."
    if isinstance(exc, (ValueError, ValidationError)):
        return "The model returned output the scanner couldn't use. Try the scan again."
    return f"Something went wrong ({type(exc).__name__}). Try the scan again."


class ScanJob:
    def __init__(self, supplier_name: str, context: dict | None):
        self.id = uuid.uuid4().hex
        self.supplier_name = supplier_name
        self.context = context
        self.status = "running"  # "running" | "done" | "error"
        self.report: dict | None = None
        self.report_path: str | None = None
        self.error: str | None = None
        self.started_at = time.time()
        self.finished = threading.Event()
        self._lines: list[str] = []
        self._lock = threading.Lock()

    def log(self, message) -> None:
        with self._lock:
            self._lines.append(redact_secrets(str(message)))

    def lines(self) -> list[str]:
        with self._lock:
            return list(self._lines)

    def wait(self, timeout: float | None = None) -> bool:
        return self.finished.wait(timeout)


class ScanRunner:
    def __init__(self, scan_fn=None):
        self._scan_fn = scan_fn
        self._lock = threading.Lock()
        self._job: ScanJob | None = None

    @property
    def job(self) -> ScanJob | None:
        return self._job

    def is_running(self) -> bool:
        return self._job is not None and self._job.status == "running"

    def start(self, supplier_name: str, context: dict | None = None) -> ScanJob | None:
        """Start a scan, or return None if one is already running."""
        with self._lock:
            if self.is_running():
                return None
            job = ScanJob(supplier_name, context)
            self._job = job
        threading.Thread(target=self._work, args=(job,), daemon=True).start()
        return job

    def _work(self, job: ScanJob) -> None:
        scan_fn = self._scan_fn or pipeline.run_scan
        try:
            job.report, job.report_path = scan_fn(job.supplier_name, job.context, log=job.log)
            job.status = "done"
        except Exception as exc:
            job.error = redact_secrets(describe_error(exc))
            job.status = "error"
        finally:
            job.finished.set()
