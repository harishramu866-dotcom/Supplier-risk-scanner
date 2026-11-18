"""Streamlit dashboard for the supplier risk scanner.

Tab 1 reads every finished report from reports/ and renders an overview
table plus a per-supplier detail view. Tab 2 runs a new scan with live
progress and saves its report to reports/.

Run: streamlit run app.py
"""

import hashlib
import html
import json
import os
from pathlib import Path

import streamlit as st

from risk_scanner.context import clean_context
from risk_scanner.scan_runner import ScanRunner

APP_DIR = Path(__file__).resolve().parent
REPORTS_DIR = APP_DIR / "reports"

CATEGORY_ORDER = ["labor", "environmental", "sanctions", "financial", "legal"]

AVATAR_PALETTE = [
    "#ef4444", "#f97316", "#f59e0b", "#84cc16", "#22c55e",
    "#14b8a6", "#06b6d4", "#3b82f6", "#6366f1", "#8b5cf6",
    "#d946ef", "#ec4899",
]

RISK_COLORS = {
    "High": {"bg": "#fee2e2", "text": "#b91c1c", "dot": "#ef4444"},
    "Medium": {"bg": "#fef3c7", "text": "#92400e", "dot": "#f59e0b"},
    "Low": {"bg": "#dcfce7", "text": "#166534", "dot": "#22c55e"},
    "Unknown": {"bg": "#e5e7eb", "text": "#374151", "dot": "#9ca3af"},
}

STATUS_TO_RISK_COLOR = {"Clear": "Low", "Flagged": "High", "Unknown": "Unknown"}

CONFIDENCE_COLORS = {
    "High": {"bg": "#e0e7ff", "text": "#3730a3"},
    "Medium": {"bg": "#eef2ff", "text": "#4338ca"},
    "Low": {"bg": "#f3f4f6", "text": "#6b7280"},
}

IDENTITY_STYLES = {
    "Confirmed": {
        "bg": "#dbeafe", "text": "#1e40af", "border": "1px solid #93c5fd",
        "label": "✓ Identity confirmed",
    },
    "Ambiguous": {
        "bg": "#ffedd5", "text": "#9a3412", "border": "2px solid #f97316",
        "label": "⚠ Identity ambiguous — needs verification",
    },
    "Unverified": {
        "bg": "#f3f4f6", "text": "#4b5563", "border": "1px dashed #9ca3af",
        "label": "? Identity unverified",
    },
}

CONTEXT_FIELDS = [
    ("country", "Country"),
    ("city", "City"),
    ("industry", "Industry"),
    ("website_domain", "Website"),
    ("parent_company", "Parent company"),
]


def escape_text(text: str) -> str:
    """HTML-escape text and neutralize '$' (Streamlit's markdown renders $..$ as LaTeX math)
    before embedding LLM- or JSON-sourced text into markdown or raw HTML."""
    return html.escape(str(text), quote=True).replace("$", "&#36;")


def initials(name: str) -> str:
    words = [w for w in name.split() if w]
    return "".join(w[0].upper() for w in words[:2]) or "?"


def color_for_name(name: str) -> str:
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return AVATAR_PALETTE[int(digest, 16) % len(AVATAR_PALETTE)]


def avatar_html(name: str, size: int = 40, font_size: int = 16) -> str:
    color = color_for_name(name)
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:50%;'
        f'background:{color};display:flex;align-items:center;justify-content:center;'
        f'color:white;font-weight:600;font-size:{font_size}px;flex-shrink:0;">'
        f'{escape_text(initials(name))}</div>'
    )


def risk_badge_html(risk: str) -> str:
    c = RISK_COLORS.get(risk, RISK_COLORS["Unknown"])
    label = "⚠ Unknown — needs verification" if risk == "Unknown" else risk
    return (
        f'<span style="background:{c["bg"]};color:{c["text"]};padding:4px 12px;'
        f'border-radius:12px;font-weight:600;font-size:13px;white-space:nowrap;'
        f'display:inline-flex;align-items:center;gap:6px;">'
        f'<span style="width:8px;height:8px;border-radius:50%;background:{c["dot"]};'
        f'display:inline-block;"></span>{label}</span>'
    )


def status_badge_html(status: str) -> str:
    c = RISK_COLORS[STATUS_TO_RISK_COLOR.get(status, "Unknown")]
    label = "⚠ Unknown" if status == "Unknown" else status
    return (
        f'<span style="background:{c["bg"]};color:{c["text"]};padding:3px 10px;'
        f'border-radius:10px;font-weight:600;font-size:12px;white-space:nowrap;">'
        f'{label}</span>'
    )


def identity_badge_html(status: str) -> str:
    style = IDENTITY_STYLES.get(status, IDENTITY_STYLES["Unverified"])
    return (
        f'<span style="background:{style["bg"]};color:{style["text"]};border:{style["border"]};'
        f'padding:3px 12px;border-radius:12px;font-weight:600;font-size:13px;'
        f'white-space:nowrap;">{style["label"]}</span>'
    )


def context_chips_html(context: dict) -> str:
    """One chip per supplier_context field that has a value; '' when there are none."""
    chips = []
    for key, label in CONTEXT_FIELDS:
        value = context.get(key)
        if isinstance(value, str) and value.strip():
            chips.append(
                f'<span style="background:#f3f4f6;color:#374151;padding:4px 10px;border-radius:8px;'
                f'font-size:13px;"><span style="color:#6b7280;">{label}</span> '
                f'<strong>{escape_text(value)}</strong></span>'
            )
    if not chips:
        return ""
    return f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{"".join(chips)}</div>'


def confidence_badge_html(confidence: str) -> str:
    c = CONFIDENCE_COLORS.get(confidence, CONFIDENCE_COLORS["Low"])
    return (
        f'<span style="background:{c["bg"]};color:{c["text"]};padding:2px 8px;'
        f'border-radius:8px;font-size:11px;font-weight:600;white-space:nowrap;">'
        f'{confidence} confidence</span>'
    )


@st.cache_data
def load_reports(mtime_key: float) -> list[dict]:
    """mtime_key busts the cache when reports/ changes (see call site)."""
    reports = []
    for path in sorted(REPORTS_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        data["_path"] = str(path)
        reports.append(data)
    return reports


def reports_mtime_key() -> float:
    if not REPORTS_DIR.exists():
        return 0.0
    return max((p.stat().st_mtime for p in REPORTS_DIR.glob("*.json")), default=0.0)


def render_overview(reports: list[dict]) -> None:
    st.subheader("Supplier Reports")

    total = len(reports)
    high_count = sum(1 for r in reports if r.get("overall_risk") == "High")
    unknown_count = sum(1 for r in reports if r.get("overall_risk") == "Unknown")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Suppliers Scanned", total)
    m2.metric("High Risk", high_count)
    m3.metric("Unknown Risk", unknown_count)

    st.divider()

    selected_risk = st.selectbox("Filter by risk level", ["All", "High", "Medium", "Low", "Unknown"])
    filtered = reports if selected_risk == "All" else [r for r in reports if r.get("overall_risk") == selected_risk]

    if not filtered:
        st.info("No suppliers match this filter.")
        return

    header = st.columns([0.6, 3, 2, 2, 1])
    header[1].markdown("**Supplier**")
    header[2].markdown("**Overall Risk**")
    header[3].markdown("**Date Scanned**")

    st.markdown('<hr style="margin:4px 0 8px 0;">', unsafe_allow_html=True)

    for report in filtered:
        row = st.columns([0.6, 3, 2, 2, 1], vertical_alignment="center")
        row[0].markdown(avatar_html(report.get("supplier_name", "?"), size=36, font_size=14), unsafe_allow_html=True)
        row[1].markdown(f"**{escape_text(report.get('supplier_name', 'Unknown supplier'))}**")
        row[2].markdown(risk_badge_html(report.get("overall_risk", "Unknown")), unsafe_allow_html=True)
        row[3].write(report.get("search_date", "—"))
        if row[4].button("View", key=f"view_{report['_path']}"):
            st.session_state.selected_report_path = report["_path"]
            st.session_state.view = "detail"
            st.rerun()


def render_detail(reports: list[dict]) -> None:
    report = next((r for r in reports if r["_path"] == st.session_state.selected_report_path), None)
    if report is None:
        st.session_state.view = "overview"
        st.rerun()
        return

    if st.button("← Back to overview"):
        st.session_state.view = "overview"
        st.rerun()

    st.write("")
    render_report_body(report)


def header_badges_html(report: dict) -> str:
    """Risk badge, plus the identity badge for reports that have an identity check."""
    badges = risk_badge_html(report.get("overall_risk", "Unknown"))
    identity = report.get("identity_check")
    if isinstance(identity, dict) and identity:
        badges += identity_badge_html(identity.get("status", "Unverified"))
    return f'<div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">{badges}</div>'


def summary_html(report: dict) -> str:
    summary = escape_text(report.get("summary", "No summary available."))
    return f'<div style="font-size:1.05rem;line-height:1.6;font-weight:500;">{summary}</div>'


def render_report_body(report: dict) -> None:
    # Reports saved before the identity check existed have neither field; they show as before.
    identity = report.get("identity_check")
    identity = identity if isinstance(identity, dict) else {}
    context = report.get("supplier_context")
    context = context if isinstance(context, dict) else {}

    header = st.columns([1, 5], vertical_alignment="center")
    with header[0]:
        st.markdown(avatar_html(report.get("supplier_name", "?"), size=72, font_size=26), unsafe_allow_html=True)
    with header[1]:
        st.markdown(f"## {escape_text(report.get('supplier_name', 'Unknown supplier'))}")
        st.markdown(header_badges_html(report), unsafe_allow_html=True)
        st.caption(f"Scanned on {report.get('search_date', 'unknown date')}")

    st.write("")
    st.markdown(summary_html(report), unsafe_allow_html=True)

    note = report.get("data_completeness_note")
    if note:
        st.warning(escape_text(note))

    identity_note = escape_text(identity.get("note", ""))
    if identity.get("status") == "Ambiguous":
        st.warning(f"**Identity needs verification.** {identity_note}")

    if identity or context:
        st.write("")
        st.markdown("#### Scanned with")
        chips = context_chips_html(context)
        st.markdown(
            chips or '<span style="color:#9ca3af;">No supplier context was supplied.</span>',
            unsafe_allow_html=True,
        )
        if identity_note and identity.get("status") != "Ambiguous":
            st.caption(identity_note)

    st.write("")
    st.markdown("#### Categories")

    categories = report.get("categories", {})
    for category in CATEGORY_ORDER:
        cat_data = categories.get(category, {"status": "Unknown", "findings": []})
        with st.container(border=True):
            title_row = st.columns([4, 1], vertical_alignment="center")
            title_row[0].markdown(f"**{category.capitalize()}**")
            title_row[1].markdown(status_badge_html(cat_data.get("status", "Unknown")), unsafe_allow_html=True)

            findings = cat_data.get("findings", [])
            if not findings:
                st.caption("No findings.")
            else:
                for finding in findings:
                    claim = escape_text(finding.get("claim", ""))
                    source = escape_text(finding.get("source", "#"))
                    confidence = finding.get("confidence", "Low")
                    st.markdown(
                        f'<div style="margin:10px 0;padding-bottom:10px;'
                        f'border-bottom:1px solid #e5e7eb;">'
                        f'<div style="margin-bottom:6px;">{claim}</div>'
                        f'<div style="display:flex;align-items:center;gap:10px;">'
                        f'{confidence_badge_html(confidence)}'
                        f'<a href="{source}" target="_blank" style="font-size:12px;">Source ↗</a>'
                        f'</div></div>',
                        unsafe_allow_html=True,
                    )


def render_supplier_reports_tab() -> None:
    if "view" not in st.session_state:
        st.session_state.view = "overview"
    if "selected_report_path" not in st.session_state:
        st.session_state.selected_report_path = None

    reports = load_reports(reports_mtime_key())

    if not reports:
        st.info("No reports found in reports/ yet. Run scripts/run_report.py to generate one.")
        return

    if st.session_state.view == "detail" and st.session_state.selected_report_path:
        render_detail(reports)
    else:
        render_overview(reports)


@st.cache_resource
def get_scan_runner() -> ScanRunner:
    """One runner shared by every session, so only one paid scan can run at a time."""
    return ScanRunner()


def render_scan_progress(runner: ScanRunner) -> None:
    job = runner.job
    if job is None:
        return

    name = escape_text(job.supplier_name)
    label = {"running": f"Scanning {name}...", "done": f"Scan of {name} complete", "error": f"Scan of {name} failed"}
    state = {"running": "running", "done": "complete", "error": "error"}
    with st.status(label[job.status], state=state[job.status], expanded=True):
        st.code("\n".join(job.lines()) or "Starting the scan...", language=None, wrap_lines=True)

    if job.status == "running":
        return

    # The form and the Supplier Reports tab were drawn while the scan was still running,
    # so redraw the whole page once: this re-enables Run scan and lists the new report.
    if st.session_state.get("scan_finalized_job") != job.id:
        st.session_state.scan_finalized_job = job.id
        load_reports.clear()
        st.rerun()

    if job.status == "error":
        st.error(escape_text(job.error))
        st.caption("The trace above shows how far the scan got. Nothing was saved to reports/.")
        return

    report = job.report
    st.success(f"Scan complete. The report was saved as {Path(job.report_path).name}.")
    st.markdown(header_badges_html(report), unsafe_allow_html=True)
    st.write("")
    st.markdown(summary_html(report), unsafe_allow_html=True)
    st.write("")
    if st.button("Open full report", key=f"open_{job.id}"):
        st.session_state.scan_open_report_path = str(REPORTS_DIR / Path(job.report_path).name)
        st.rerun()


def render_new_scan_tab() -> None:
    runner = get_scan_runner()

    open_path = st.session_state.get("scan_open_report_path")
    if open_path:
        report = next((r for r in load_reports(reports_mtime_key()) if r["_path"] == open_path), None)
        if report is not None:
            if st.button("← Back to New Scan"):
                st.session_state.scan_open_report_path = None
                st.rerun()
            st.write("")
            render_report_body(report)
            return
        st.session_state.scan_open_report_path = None

    running = runner.is_running()
    st.subheader("New Scan")

    with st.form("new_scan_form"):
        name = st.text_input("Supplier name (required)", key="scan_name", disabled=running)
        left, right = st.columns(2)
        country = left.text_input("Country", key="scan_country", disabled=running)
        city = right.text_input("City", key="scan_city", disabled=running)
        industry = left.text_input("Industry", key="scan_industry", disabled=running)
        domain = right.text_input("Website domain", key="scan_domain", placeholder="example.com", disabled=running)
        parent = st.text_input("Parent company", key="scan_parent", disabled=running)
        submitted = st.form_submit_button("Run scan", type="primary", disabled=running)
        st.caption("Each scan uses paid API calls.")

    if submitted:
        if not name.strip():
            st.error("Please enter a supplier name before running a scan.")
        else:
            context = clean_context({
                "country": country, "city": city, "industry": industry,
                "website_domain": domain, "parent_company": parent,
            })
            if runner.start(name.strip(), context) is None:
                st.warning("A scan is already running. Wait for it to finish before starting another.")
            else:
                st.rerun()

    if runner.job is not None:
        st.write("")
        polling = st.fragment(render_scan_progress, run_every=1.0 if running else None)
        polling(runner)


def main() -> None:
    # The scan writes to output/ and reports/ relative to the working directory,
    # so pin it to the project folder no matter where Streamlit was launched from.
    os.chdir(APP_DIR)
    st.set_page_config(page_title="Supplier Risk Scanner", layout="wide")
    st.title("Supplier Risk Scanner")

    tab1, tab2 = st.tabs(["Supplier Reports", "New Scan"])
    with tab1:
        render_supplier_reports_tab()
    with tab2:
        render_new_scan_tab()


if __name__ == "__main__":
    main()
