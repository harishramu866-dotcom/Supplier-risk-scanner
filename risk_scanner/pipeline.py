"""The full scan, start to finish. The command line and the dashboard both call run_scan."""

from risk_scanner.iterative_scan import iterative_scan
from risk_scanner.report import assemble_report, save_report


def run_scan(supplier_name: str, context: dict | None = None, log=print) -> tuple[dict, str]:
    """Search, extract (retrying Unknown categories), score, summarize, and save the report.

    Every progress line goes through `log`. The report is validated before it is saved,
    so a scan that fails partway never leaves a report behind. Returns (report, report_path).
    """
    result = iterative_scan(supplier_name, context, log=log)

    log("\n=== Scoring and writing the summary ===")
    report = assemble_report(
        supplier_name,
        result["categories"],
        supplier_context=result.get("supplier_context"),
        identity_check=result["identity_check"],
    )
    path = save_report(report)
    log(f"Overall risk: {report['overall_risk']}")
    log(f"Saved report to {path}")
    return report, path
