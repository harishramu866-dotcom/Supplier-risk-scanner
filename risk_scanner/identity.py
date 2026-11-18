"""Identity check: did the search results concern the company the user meant?

Extraction reports an identity_check per category; this module validates each
one and combines them into the single report-level identity_check. Plain code,
no AI, so the same inputs always give the same result.
"""

from risk_scanner.context import clean_context

IDENTITY_STATUSES = ("Confirmed", "Ambiguous", "Unverified")

NO_CONTEXT_NOTE = "No supplier context was provided, so the company's identity could not be checked."
NO_CONFIRMATION_NOTE = (
    "Context was supplied, but no result contained a concrete match "
    "(domain, country, or parent company) to confirm the company."
)
MISSING_NOTE = "The model gave no explanation for this identity result."


def normalize_identity(raw, context: dict | None) -> dict:
    """Validate one category's identity_check. Without context the status is always Unverified."""
    if not clean_context(context):
        return {"status": "Unverified", "note": NO_CONTEXT_NOTE}

    status = raw.get("status") if isinstance(raw, dict) else None
    note = raw.get("note") if isinstance(raw, dict) else None
    if status not in IDENTITY_STATUSES:
        return {"status": "Unverified", "note": NO_CONFIRMATION_NOTE}

    note = note.strip() if isinstance(note, str) else ""
    if not note:
        note = NO_CONFIRMATION_NOTE if status == "Unverified" else MISSING_NOTE
    return {"status": status, "note": note}


def combine_identity_checks(context: dict | None, per_category: dict[str, dict]) -> dict:
    """Ambiguous in any category wins, then Confirmed, otherwise Unverified."""
    if not clean_context(context):
        return {"status": "Unverified", "note": NO_CONTEXT_NOTE}
    for status in ("Ambiguous", "Confirmed"):
        for identity in per_category.values():
            if identity["status"] == status:
                return {"status": status, "note": identity["note"]}
    return {"status": "Unverified", "note": NO_CONFIRMATION_NOTE}
