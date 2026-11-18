"""Manual test for stage 2 (search agent): run it on one real supplier and print the output.

Every run saves its result to output/<supplier>_<timestamp>.json.

Only the supplier name is required. The optional context flags help tell apart
companies with similar names.

Usage: py scripts/run_search_agent.py "Supplier Name" [--country X] [--city X]
           [--industry X] [--domain example.com] [--parent "Parent Co"]
"""

import argparse
import json

from risk_scanner.context import add_context_arguments, context_from_args
from risk_scanner.search_agent import (
    build_scan_result,
    generate_search_queries,
    run_all_searches,
    save_scan_result,
)


def main():
    parser = argparse.ArgumentParser(description="Stage 2: generate search queries and run them.")
    parser.add_argument("supplier_name", help="supplier name (required)")
    add_context_arguments(parser)
    args = parser.parse_args()
    context = context_from_args(args)

    print(f"=== Generating search queries for: {args.supplier_name} ===")
    queries = generate_search_queries(args.supplier_name, context)
    print(json.dumps(queries, indent=2))

    print("\n=== Running queries against Brave Search ===")
    raw_results = run_all_searches(queries)
    print(json.dumps(raw_results, indent=2))

    path = save_scan_result(build_scan_result(args.supplier_name, queries, raw_results, context))
    print(f"\nSaved to {path}")


if __name__ == "__main__":
    main()
