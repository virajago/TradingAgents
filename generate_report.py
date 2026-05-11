#!/usr/bin/env python3
"""
Generate a sample AI Analyst Weekly report for a given ticker.

Usage:
    python generate_report.py NVDA
    python generate_report.py AAPL 2026-05-11
    python generate_report.py MSFT --output reports/msft
    python generate_report.py NVDA --no-pdf        # Markdown only
"""
import argparse
import asyncio
import re
import sys
import textwrap
from datetime import date
from pathlib import Path


# ── PDF generation ────────────────────────────────────────────────────────────

def generate_pdf(report_md: str, output_path: Path, ticker: str, trade_date: str) -> None:
    """Convert the Markdown report to a clean PDF using fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        print("  ⚠ fpdf2 not installed — skipping PDF. Run: uv pip install fpdf2")
        return

    class ReportPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(100, 100, 100)
            self.cell(0, 8, f"AI ANALYST WEEKLY  —  {ticker}  —  {trade_date}", align="L")
            self.set_text_color(0, 0, 0)
            self.ln(4)
            self.set_draw_color(220, 220, 220)
            self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
            self.ln(4)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, "Educational research only. Not investment advice. Not a registered investment adviser.", align="L")
            self.cell(0, 10, f"Page {self.page_no()}", align="R")

    pdf = ReportPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(20, 20, 20)
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Parse and render Markdown line by line
    lines = report_md.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]

        # Skip the blockquote disclaimer block (already in footer)
        if line.startswith("> "):
            i += 1
            continue

        # H1
        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(26, 77, 140)  # accent blue
            pdf.multi_cell(0, 10, line[2:].strip())
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

        # H2
        elif line.startswith("## "):
            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(26, 77, 140)
            pdf.multi_cell(0, 8, line[3:].strip())
            pdf.set_text_color(0, 0, 0)
            # Underline
            pdf.set_draw_color(200, 210, 230)
            y = pdf.get_y()
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(3)

        # H3
        elif line.startswith("### "):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 7, line[4:].strip())
            pdf.set_text_color(0, 0, 0)
            pdf.ln(1)

        # Horizontal rule
        elif line.strip() == "---":
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)

        # Bold verdict line: **Rating**: ...
        elif line.startswith("**Rating**") or line.startswith("**Verdict**"):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_fill_color(232, 245, 238)   # light green bg
            pdf.set_text_color(26, 107, 60)     # bullish green
            clean = _strip_md(line)
            pdf.multi_cell(0, 8, clean, fill=True)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(2)

        # Bold line
        elif line.startswith("**") and line.endswith("**") and len(line) > 4:
            pdf.set_font("Helvetica", "B", 10)
            pdf.multi_cell(0, 6, _strip_md(line))
            pdf.ln(1)

        # Bullet
        elif line.strip().startswith("- ") or line.strip().startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            text = _strip_md(line.strip()[2:])
            pdf.set_x(pdf.l_margin + 5)
            pdf.cell(4, 6, chr(149))  # bullet char
            pdf.multi_cell(0, 6, text)

        # Empty line
        elif line.strip() == "":
            pdf.ln(2)

        # Normal paragraph text
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(30, 30, 30)
            clean = _strip_md(line)
            if clean.strip():
                pdf.multi_cell(0, 6, clean)
                pdf.ln(1)

        i += 1

    pdf.output(str(output_path))


def _strip_md(text: str) -> str:
    """Remove Markdown formatting characters for plain PDF rendering."""
    # Bold/italic
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"_(.+?)_", r"\1", text)
    # Inline code
    text = re.sub(r"`(.+?)`", r"\1", text)
    # Links [text](url) → text
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1", text)
    return text


# ── Main analysis + report generation ────────────────────────────────────────

async def run(ticker: str, trade_date: str, output_stem: str, pdf: bool) -> None:
    from tradingagents.pipeline.runner import run_analysis

    print(f"\n  AI Analyst Weekly — Sample Report Generator")
    print(f"  {'─' * 44}")
    print(f"  Ticker:     {ticker.upper()}")
    print(f"  Date:       {trade_date}")
    print(f"  Analysts:   Fundamental · Technical · Sentiment · News")
    print(f"  Synthesis:  Bull/Bear Debate → Research Manager → Portfolio Manager")
    print()

    agents_done = []

    async def on_agent_complete(agent_name, state):
        agents_done.append(agent_name)
        summary = state.agent_summaries.get(agent_name, "")
        suffix = f" — {summary}" if summary else ""
        print(f"  [{len(agents_done)}/8] ✓ {agent_name}{suffix}")

    state = await run_analysis(
        ticker=ticker,
        trade_date=trade_date,
        on_agent_complete=on_agent_complete,
    )

    # ── Build Markdown ────────────────────────────────────────────────────────

    verdict_first_line = (state.final_decision or "").split("\n")[0]

    report_md = f"""# AI Analyst Weekly — {ticker.upper()} Research Report
Generated: {trade_date}

> **Educational research only. Not investment advice.**
> AI-generated analysis for informational purposes only. Nothing here
> constitutes a recommendation to buy, sell, or hold any security.
> Always consult a licensed financial advisor before making investment decisions.

---

## Verdict

{state.final_decision or "Analysis unavailable — check logs."}

---

## Fundamental Analysis

{state.fundamentals_report or "Unavailable."}

---

## Technical Analysis

{state.market_report or "Unavailable."}

---

## News & Macro

{state.news_report or "Unavailable."}

---

## Sentiment

{state.sentiment_report or "Unavailable."}

---

## Bull vs. Bear Debate

{state.bull_case or "Unavailable."}

{state.bear_case or ""}

---

## Research Manager Summary

{state.investment_plan or "Unavailable."}

---

## Trader Proposal

{state.trader_proposal or "Unavailable."}

---

*Generated by AI Analyst Weekly · {trade_date} · Not investment advice*
"""

    # ── Save Markdown ─────────────────────────────────────────────────────────

    md_path = Path(f"{output_stem}.md")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(report_md, encoding="utf-8")

    # ── Save PDF ──────────────────────────────────────────────────────────────

    if pdf:
        pdf_path = Path(f"{output_stem}.pdf")
        generate_pdf(report_md, pdf_path, ticker, trade_date)

    # ── Summary ───────────────────────────────────────────────────────────────

    print()
    print(f"  ✓ Markdown  → {md_path.resolve()}")
    if pdf:
        pdf_path = Path(f"{output_stem}.pdf")
        if pdf_path.exists():
            print(f"  ✓ PDF       → {pdf_path.resolve()}")
    print()
    print(f"  {verdict_first_line}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Generate an AI Analyst Weekly sample report (Markdown + PDF)"
    )
    parser.add_argument("ticker", help="Stock ticker symbol, e.g. NVDA")
    parser.add_argument(
        "trade_date",
        nargs="?",
        default=str(date.today()),
        help="Analysis date YYYY-MM-DD (default: today)",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output path stem, no extension (default: reports/<TICKER>_<DATE>)",
    )
    parser.add_argument(
        "--no-pdf",
        action="store_true",
        help="Skip PDF generation, produce Markdown only",
    )
    args = parser.parse_args()

    ticker = args.ticker.upper().strip()
    trade_date = args.trade_date
    stem = args.output or f"reports/{ticker}_{trade_date}"

    asyncio.run(run(ticker, trade_date, stem, pdf=not args.no_pdf))


if __name__ == "__main__":
    main()
