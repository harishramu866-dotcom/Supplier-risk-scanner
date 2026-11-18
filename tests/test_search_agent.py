from risk_scanner.search_agent import build_scan_result, generate_search_queries

QUERIES = {c: [f"{c} query"] for c in ("labor", "environmental", "sanctions", "financial", "legal")}
CONTEXT = {"country": "Vietnam", "city": "Hanoi", "industry": "Textiles", "website_domain": "acme.vn", "parent_company": "Acme Group"}


def test_prompt_includes_every_supplied_context_field(fake_client):
    client = fake_client(QUERIES)
    generate_search_queries("Acme Textiles", CONTEXT, client)
    prompt = client.prompts[0]
    for line in (
        "- Country: Vietnam",
        "- City: Hanoi",
        "- Industry: Textiles",
        "- Website domain: acme.vn",
        "- Parent company: Acme Group",
    ):
        assert line in prompt


def test_prompt_tells_the_model_how_to_use_context(fake_client):
    client = fake_client(QUERIES)
    generate_search_queries("Acme Textiles", CONTEXT, client)
    prompt = " ".join(client.prompts[0].split())
    assert "If a parent company is given in the context, search it directly" in prompt
    assert "If a website domain is given, use it in a few queries per" in prompt
    assert "If a country is given, use it where it helps" in prompt
    assert "Do NOT append the industry or the city to every query" in prompt
    assert "verifying results later, not blanket search terms" in prompt


def test_prompt_without_context(fake_client):
    client = fake_client(QUERIES)
    assert generate_search_queries("Acme Textiles", None, client) == QUERIES
    assert "Context: none supplied." in client.prompts[0]


def test_scan_result_includes_context_only_when_given():
    assert "supplier_context" not in build_scan_result("Acme", QUERIES, {}, None)
    assert "supplier_context" not in build_scan_result("Acme", QUERIES, {}, {"city": " "})
    assert build_scan_result("Acme", QUERIES, {}, {"country": "Vietnam"})["supplier_context"] == {"country": "Vietnam"}
