import argparse

from risk_scanner.context import (
    add_context_arguments,
    clean_context,
    context_from_args,
    format_context_block,
    normalize_domain,
)


def parse(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("supplier_name")
    add_context_arguments(parser)
    return parser.parse_args(argv)


def test_normalize_domain_strips_scheme_www_and_path():
    assert normalize_domain("https://www.Example.com/about?x=1") == "example.com"
    assert normalize_domain("example.com") == "example.com"
    assert normalize_domain("  WWW.Example.co.uk/ ") == "example.co.uk"


def test_clean_context_drops_blank_missing_and_unknown_fields():
    assert clean_context({"country": " Taiwan ", "city": "  ", "industry": None, "bogus": "x"}) == {
        "country": "Taiwan"
    }
    assert clean_context(None) == {}
    assert clean_context({}) == {}


def test_clean_context_normalizes_the_domain():
    assert clean_context({"website_domain": "https://www.foxconn.com/en"}) == {"website_domain": "foxconn.com"}


def test_clean_context_drops_a_domain_that_normalizes_to_nothing():
    assert clean_context({"website_domain": "https:///"}) == {}


def test_format_context_block_with_and_without_context():
    assert format_context_block(None) == "Context: none supplied."
    block = format_context_block({"country": "Taiwan", "parent_company": "Hon Hai"})
    assert "- Country: Taiwan" in block
    assert "- Parent company: Hon Hai" in block
    assert "City" not in block


def test_cli_with_only_the_supplier_name_gives_empty_context():
    args = parse(["Acme Textiles"])
    assert args.supplier_name == "Acme Textiles"
    assert context_from_args(args) == {}


def test_cli_with_all_context_flags():
    args = parse([
        "Acme Textiles", "--country", "Vietnam", "--city", "Hanoi", "--industry", "Textiles",
        "--domain", "https://www.acme.vn/", "--parent", "Acme Group",
    ])
    assert context_from_args(args) == {
        "country": "Vietnam",
        "city": "Hanoi",
        "industry": "Textiles",
        "website_domain": "acme.vn",
        "parent_company": "Acme Group",
    }


def test_cli_with_some_context_flags():
    assert context_from_args(parse(["Acme", "--country", "India"])) == {"country": "India"}
