"""Run a full scan from the command line: search, extract (retrying Unknown categories),
score, summarize, and save the report to reports/. The dashboard's New Scan tab calls the
same function.

Only the supplier name is required. The optional context flags help tell apart
companies with similar names.

Usage: py -m scripts.run_iterative_scan "Supplier Name" [--country X] [--city X]
           [--industry X] [--domain example.com] [--parent "Parent Co"]
"""

import argparse

from risk_scanner.context import add_context_arguments, context_from_args
from risk_scanner.pipeline import run_scan


def main():
    parser = argparse.ArgumentParser(description="Scan a supplier and save its report.")
    parser.add_argument("supplier_name", help="supplier name (required)")
    add_context_arguments(parser)
    args = parser.parse_args()
    run_scan(args.supplier_name, context_from_args(args))


if __name__ == "__main__":
    main()
