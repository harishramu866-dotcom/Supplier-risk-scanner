from app import context_chips_html, identity_badge_html


def test_ambiguous_badge_is_flagged_as_needing_verification():
    badge = identity_badge_html("Ambiguous")
    assert "needs verification" in badge
    assert "needs verification" not in identity_badge_html("Confirmed")
    assert "needs verification" not in identity_badge_html("Unverified")


def test_the_three_identity_badges_look_different():
    badges = {identity_badge_html(s) for s in ("Confirmed", "Ambiguous", "Unverified")}
    assert len(badges) == 3
    assert "Identity confirmed" in identity_badge_html("Confirmed")
    assert "Identity unverified" in identity_badge_html("Unverified")


def test_an_unrecognised_status_falls_back_to_unverified():
    assert identity_badge_html("Whatever") == identity_badge_html("Unverified")


def test_context_chips_show_only_fields_with_values():
    chips = context_chips_html({"country": "Taiwan", "city": "", "website_domain": "foxconn.com"})
    assert "Taiwan" in chips and "foxconn.com" in chips
    assert "City" not in chips and "Industry" not in chips


def test_context_chips_are_empty_without_context():
    assert context_chips_html({}) == ""
    assert context_chips_html({"city": "  "}) == ""


def test_context_chips_escape_html_and_dollar_signs():
    chips = context_chips_html({"parent_company": "<script>alert(1)</script> $5"})
    assert "<script>" not in chips
    assert "&lt;script&gt;" in chips
    assert "$" not in chips
