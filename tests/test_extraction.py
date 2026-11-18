import json

import pytest
from jsonschema import ValidationError

from risk_scanner.extraction import (
    extract_all_categories,
    extract_category_findings,
    extract_category_with_identity,
    save_extraction_result,
)

RESULTS = {"query": [{"title": "Strike at plant", "snippet": "Workers walked out.", "url": "https://example.com/a"}]}
CONTEXT = {"country": "Taiwan", "website_domain": "foxconn.com", "parent_company": "Hon Hai"}
FINDING = {"claim": "Workers went on strike.", "source": "https://example.com/a", "confidence": "High"}


def model_output(status="Flagged", findings=(FINDING,), identity=("Confirmed", "Domain matches.")):
    output = {"status": status, "findings": list(findings)}
    if identity:
        output["identity_check"] = {"status": identity[0], "note": identity[1]}
    return output


def test_prompt_compares_results_against_the_supplied_context(fake_client):
    client = fake_client(model_output())
    extract_category_with_identity("Foxconn", "labor", RESULTS, CONTEXT, client)
    prompt = " ".join(client.prompts[0].split())
    assert "- Country: Taiwan" in prompt
    assert "- Website domain: foxconn.com" in prompt
    assert "- Parent company: Hon Hai" in prompt
    assert "Compare each result against the supplied context" in prompt
    assert "Discard results that clearly point to a different entity" in prompt
    assert "Do NOT attribute findings to either company" in prompt
    assert '"Confirmed" only if something concrete supports' in prompt
    assert "always if no context was supplied" in prompt


def test_prompt_without_context_says_none_supplied(fake_client):
    client = fake_client(model_output(identity=None))
    extract_category_with_identity("Foxconn", "labor", RESULTS, None, client)
    assert "Context: none supplied." in client.prompts[0]


def test_confirmed_result_keeps_findings_and_strips_identity_from_the_category(fake_client):
    category, identity = extract_category_with_identity(
        "Foxconn", "labor", RESULTS, CONTEXT, fake_client(model_output())
    )
    assert category == {"status": "Flagged", "findings": [FINDING]}
    assert identity == {"status": "Confirmed", "note": "Domain matches."}


def test_ambiguous_identity_forces_unknown_and_drops_findings(fake_client):
    client = fake_client(model_output(identity=("Ambiguous", "Two companies share this name.")))
    category, identity = extract_category_with_identity("Acme", "legal", RESULTS, CONTEXT, client)
    assert category == {"status": "Unknown", "findings": []}
    assert identity == {"status": "Ambiguous", "note": "Two companies share this name."}


def test_no_context_forces_unverified_even_if_the_model_says_confirmed(fake_client):
    category, identity = extract_category_with_identity(
        "Acme", "labor", RESULTS, None, fake_client(model_output(identity=("Confirmed", "Looks right.")))
    )
    assert identity["status"] == "Unverified"
    assert category["status"] == "Flagged"


def test_missing_identity_in_model_output_is_unverified(fake_client):
    _, identity = extract_category_with_identity(
        "Acme", "labor", RESULTS, CONTEXT, fake_client(model_output(identity=None))
    )
    assert identity["status"] == "Unverified"


def test_extract_category_findings_returns_only_the_category(fake_client):
    assert extract_category_findings("Foxconn", "labor", RESULTS, CONTEXT, fake_client(model_output())) == {
        "status": "Flagged",
        "findings": [FINDING],
    }


def test_invalid_category_output_still_fails_schema_validation(fake_client):
    with pytest.raises(ValidationError):
        extract_category_with_identity("Foxconn", "labor", RESULTS, CONTEXT, fake_client(model_output(status="Maybe")))


def test_save_extraction_result_includes_context_and_identity_only_when_given(tmp_path):
    categories = {"labor": {"status": "Unknown", "findings": []}}

    plain = json.loads(open(save_extraction_result("Acme", categories, output_dir=str(tmp_path))).read())
    assert set(plain) == {"supplier_name", "categories"}

    identity = {"status": "Confirmed", "note": "Domain matches."}
    full = json.loads(
        open(save_extraction_result("Acme", categories, CONTEXT, identity, output_dir=str(tmp_path))).read()
    )
    assert full["supplier_context"] == CONTEXT
    assert full["identity_check"] == identity


def test_extract_all_categories_combines_identity_and_saves(fake_client, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("risk_scanner.extraction.anthropic.Anthropic", lambda: fake_client(model_output()))
    categories, identity_check = extract_all_categories("Foxconn", {"labor": RESULTS, "legal": RESULTS}, CONTEXT)
    assert set(categories) == {"labor", "legal"}
    assert identity_check["status"] == "Confirmed"
    saved = json.loads(next((tmp_path / "output").glob("*_extraction_*.json")).read_text(encoding="utf-8"))
    assert saved["identity_check"]["status"] == "Confirmed"
    assert saved["supplier_context"] == CONTEXT
