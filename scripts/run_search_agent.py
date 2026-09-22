"""Manual test for stage 2 (search agent): run it on one real supplier and print the output.

Usage: py scripts/run_search_agent.py "Supplier Name" ["optional context"]
"""

import json
import sys

from risk_scanner.search_agent import generate_search_queries, run_all_searches


def main():
    if len(sys.argv) < 2:
        print('Usage: py scripts/run_search_agent.py "Supplier Name" ["optional context"]')
        sys.exit(1)

    supplier_name = sys.argv[1]
    context = sys.argv[2] if len(sys.argv) > 2 else None

    print(f"=== Generating search queries for: {supplier_name} ===")
    queries = generate_search_queries(supplier_name, context)
    print(json.dumps(queries, indent=2))

    print("\n=== Running queries against Brave Search ===")
    raw_results = run_all_searches(queries)
    print(json.dumps(raw_results, indent=2))


if __name__ == "__main__":
    main()
