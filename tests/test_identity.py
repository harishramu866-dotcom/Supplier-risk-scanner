from risk_scanner.identity import (
    NO_CONFIRMATION_NOTE,
    NO_CONTEXT_NOTE,
    combine_identity_checks,
    normalize_identity,
)

CONTEXT = {"country": "Taiwan", "website_domain": "foxconn.com"}


def identity(status, note="Because."):
    return {"status": status, "note": note}


def test_normalize_passes_through_a_valid_result():
    raw = identity("Confirmed", "Domain foxconn.com matches.")
    assert normalize_identity(raw, CONTEXT) == raw


def test_normalize_forces_unverified_when_no_context_was_supplied():
    assert normalize_identity(identity("Confirmed"), None) == identity("Unverified", NO_CONTEXT_NOTE)
    assert normalize_identity(identity("Ambiguous"), {}) == identity("Unverified", NO_CONTEXT_NOTE)
    assert normalize_identity(identity("Confirmed"), {"city": "  "}) == identity("Unverified", NO_CONTEXT_NOTE)


def test_normalize_treats_missing_or_invalid_output_as_unverified():
    for raw in (None, "Confirmed", {}, {"status": "Probably", "note": "x"}, {"note": "x"}):
        assert normalize_identity(raw, CONTEXT) == identity("Unverified", NO_CONFIRMATION_NOTE)


def test_normalize_fills_in_a_missing_note():
    assert normalize_identity({"status": "Unverified"}, CONTEXT)["note"] == NO_CONFIRMATION_NOTE
    assert normalize_identity({"status": "Confirmed", "note": "  "}, CONTEXT)["note"]


def test_combine_without_context_is_unverified():
    per_category = {"labor": identity("Confirmed"), "legal": identity("Ambiguous")}
    assert combine_identity_checks(None, per_category) == identity("Unverified", NO_CONTEXT_NOTE)


def test_combine_all_unverified_is_unverified():
    per_category = {c: identity("Unverified") for c in ("labor", "legal")}
    assert combine_identity_checks(CONTEXT, per_category) == identity("Unverified", NO_CONFIRMATION_NOTE)


def test_combine_any_confirmed_is_confirmed():
    per_category = {"labor": identity("Unverified"), "legal": identity("Confirmed", "Parent matches.")}
    assert combine_identity_checks(CONTEXT, per_category) == identity("Confirmed", "Parent matches.")


def test_combine_ambiguous_beats_confirmed():
    per_category = {
        "labor": identity("Confirmed", "Domain matches."),
        "sanctions": identity("Ambiguous", "Two companies share this name."),
    }
    assert combine_identity_checks(CONTEXT, per_category) == identity("Ambiguous", "Two companies share this name.")
