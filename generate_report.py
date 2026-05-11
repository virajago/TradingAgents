#!/usr/bin/env python3
"""
Generate a styled HTML + PDF research report for a given ticker.

Usage:
    python generate_report.py NVDA
    python generate_report.py AAPL 2026-05-11
    python generate_report.py MSFT --output reports/msft
    python generate_report.py NVDA --no-pdf
"""
import argparse
import asyncio
import re
from datetime import date
from pathlib import Path


# ── Verdict helpers ───────────────────────────────────────────────────────────

def _verdict_color(decision: str) -> tuple[str, str]:
    """Return (css-class, label) based on the first word of the decision."""
    upper = (decision or "").upper()
    if "BUY" in upper or "BULLISH" in upper or "OVERWEIGHT" in upper:
        return "bullish", "BULLISH"
    if "SELL" in upper or "BEARISH" in upper or "UNDERWEIGHT" in upper:
        return "bearish", "BEARISH"
    return "neutral", "NEUTRAL"


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _is_separator_row(line: str) -> bool:
    """Detect Markdown table separator: | :--- | :--- |"""
    return _is_table_row(line) and all(
        c in ":-| " for c in line.strip()
    )


def _parse_table_rows(lines: list, start: int) -> tuple[str, int]:
    """Parse a Markdown pipe table starting at index `start`. Returns (html, next_idx)."""
    rows = []
    i = start
    while i < len(lines) and _is_table_row(lines[i]):
        rows.append(lines[i])
        i += 1

    if not rows:
        return "", start

    # Split each row into cells
    def parse_cells(row: str) -> list[str]:
        parts = row.strip().strip("|").split("|")
        return [_inline_md(c.strip()) for c in parts]

    def _looks_numeric(text: str) -> bool:
        """True if cell content is a pure financial value: ratio, percentage, price."""
        plain = re.sub(r"<[^>]+>", "", text).strip()
        if not plain or len(plain) > 30:
            return False
        patterns = [
            r"^\$[\d,\.\s\-]+$",         # $5.33, $120.28 - $222.30
            r"^~?\$[\d,\.]+",            # ~$96.7 Billion (starts with ~$)
            r"^[\d,\.]+%$",              # 101.5%, 73%
            r"^[\d,\.]+$",               # 19.44, 0.68, 3.905
            r"^\d{4}-\d{2}-\d{2}$",      # 2026-05-12
            r"^N/A$",
            r"^[\d,\.]+ (B|M|K|T|Trillion|Billion|Million)$",  # 215.94 Billion
        ]
        return any(re.match(p, plain, re.IGNORECASE) for p in patterns)

    # First row = header, second row may be separator
    header_cells = parse_cells(rows[0])
    body_start = 1
    if len(rows) > 1 and _is_separator_row(rows[1]):
        body_start = 2

    header_html = "".join(f"<th>{c}</th>" for c in header_cells)
    body_html = ""
    for row in rows[body_start:]:
        if _is_separator_row(row):
            continue
        cells = parse_cells(row)
        while len(cells) < len(header_cells):
            cells.append("")
        tds = []
        for idx, cell in enumerate(cells[:len(header_cells)]):
            css = " numeric" if idx > 0 and _looks_numeric(cell) else ""
            tds.append(f'<td class="{css.strip()}">{cell}</td>' if css.strip() else f"<td>{cell}</td>")
        body_html += f"<tr>{''.join(tds)}</tr>\n"

    table_html = (
        f'<table class="data-table">'
        f"<thead><tr>{header_html}</tr></thead>"
        f"<tbody>{body_html}</tbody>"
        f"</table>"
    )
    return table_html, i


def _md_to_html(text: str) -> str:
    """Markdown → HTML including pipe tables, bullets, headings, inline styling."""
    if not text:
        return "<p><em>Unavailable.</em></p>"

    lines = text.split("\n")
    out = []
    in_ul = False
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Markdown pipe table
        if _is_table_row(stripped):
            if in_ul:
                out.append("</ul>")
                in_ul = False
            table_html, i = _parse_table_rows(lines, i)
            out.append(table_html)
            continue

        # Bullet list
        if stripped.startswith("- ") or stripped.startswith("* "):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            content = _inline_md(stripped[2:])
            out.append(f"  <li>{content}</li>")
            i += 1
            continue

        # Close list if needed
        if in_ul and stripped:
            out.append("</ul>")
            in_ul = False

        # Headings
        if stripped.startswith("### "):
            out.append(f"<h4>{_inline_md(stripped[4:])}</h4>")
        elif stripped.startswith("## "):
            out.append(f"<h3>{_inline_md(stripped[3:])}</h3>")
        elif stripped.startswith("# "):
            out.append(f"<h3>{_inline_md(stripped[2:])}</h3>")
        elif stripped == "---":
            out.append("<hr>")
        elif not stripped:
            if in_ul:
                out.append("</ul>")
                in_ul = False
            out.append("")
        else:
            out.append(f"<p>{_inline_md(stripped)}</p>")

        i += 1

    if in_ul:
        out.append("</ul>")

    return "\n".join(out)


def _inline_md(text: str) -> str:
    """Convert inline Markdown (bold, italic, code) to HTML."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>",          text)
    text = re.sub(r"`(.+?)`",       r"<code>\1</code>",       text)
    text = re.sub(r"\[(.+?)\]\(.+?\)", r"\1",                 text)
    return text


# ── HTML report template ──────────────────────────────────────────────────────

def build_html(ticker: str, trade_date: str, state) -> str:
    verdict_class, verdict_label = _verdict_color(state.final_decision or "")

    def section(title: str, content: str) -> str:
        return f"""
        <section>
          <h2>{title}</h2>
          <div class="section-body">
            {_md_to_html(content)}
          </div>
        </section>"""

    debate_html = ""
    if state.bull_case:
        debate_html += f"""
        <div class="debate-side bull">
          <div class="debate-label">Bull Case</div>
          {_md_to_html(state.bull_case)}
        </div>"""
    if state.bear_case:
        debate_html += f"""
        <div class="debate-side bear">
          <div class="debate-label">Bear Case</div>
          {_md_to_html(state.bear_case)}
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{ticker} Research Report — AI Analyst Weekly</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=DM+Sans:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:             #fafafa;
    --surface:        #ffffff;
    --surface-2:      #f4f4f4;
    --border:         #e0e0e0;
    --text-primary:   #1a1a1a;
    --text-secondary: #4a4a4a;
    --text-tertiary:  #8a8a8a;
    --accent:         #1e4d8c;
    --bullish:        #1a6b3c;
    --bullish-bg:     #e8f5ee;
    --bearish:        #8b1a1a;
    --bearish-bg:     #fbeaea;
    --neutral:        #4a4a4a;
    --neutral-bg:     #f0f0f0;
    --font-display:   'Playfair Display', Georgia, serif;
    --font-body:      'Source Serif 4', Georgia, serif;
    --font-ui:        'DM Sans', system-ui, sans-serif;
    --font-mono:      'JetBrains Mono', monospace;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: var(--font-body);
    font-size: 16px;
    line-height: 1.65;
    background: var(--bg);
    color: var(--text-primary);
    -webkit-font-smoothing: antialiased;
  }}

  /* ── Report shell ── */
  .report {{
    max-width: 820px;
    margin: 0 auto;
    background: var(--surface);
    border-left: 1px solid var(--border);
    border-right: 1px solid var(--border);
    min-height: 100vh;
  }}

  /* ── Header ── */
  .report-header {{
    padding: 48px 56px 36px;
    border-bottom: 2px solid var(--border);
  }}
  .report-brand {{
    font-family: var(--font-ui);
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--text-tertiary);
    margin-bottom: 20px;
  }}
  .report-ticker {{
    font-family: var(--font-display);
    font-size: 52px;
    font-weight: 900;
    color: var(--text-primary);
    letter-spacing: -0.02em;
    line-height: 1;
    margin-bottom: 8px;
  }}
  .report-meta {{
    font-family: var(--font-ui);
    font-size: 14px;
    color: var(--text-tertiary);
    margin-bottom: 28px;
  }}

  /* ── Verdict badge ── */
  .verdict-block {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 20px;
    border-radius: 4px;
    margin-bottom: 4px;
  }}
  .verdict-block.bullish {{ background: var(--bullish-bg); border: 1px solid #b8dfc8; }}
  .verdict-block.bearish {{ background: var(--bearish-bg); border: 1px solid #e8b4b4; }}
  .verdict-block.neutral {{ background: var(--neutral-bg); border: 1px solid var(--border); }}
  .verdict-badge {{
    font-family: var(--font-ui);
    font-size: 13px;
    font-weight: 700;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    padding: 6px 14px;
    border-radius: 3px;
    flex-shrink: 0;
  }}
  .bullish .verdict-badge {{ color: var(--bullish); background: #c8ecd6; }}
  .bearish .verdict-badge {{ color: var(--bearish); background: #f5c6c6; }}
  .neutral .verdict-badge {{ color: var(--neutral); background: #ddd; }}
  .verdict-summary {{
    font-family: var(--font-body);
    font-size: 15px;
    color: var(--text-primary);
    line-height: 1.5;
  }}

  /* ── Sections ── */
  section {{
    padding: 36px 56px;
    border-bottom: 1px solid var(--surface-2);
  }}
  section:last-of-type {{ border-bottom: none; }}

  h2 {{
    font-family: var(--font-display);
    font-size: 22px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 6px;
  }}
  h3, h4 {{
    font-family: var(--font-ui);
    font-size: 13px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--text-tertiary);
    margin: 20px 0 8px;
  }}
  .section-rule {{
    height: 1px;
    background: var(--border);
    margin-bottom: 20px;
  }}
  .section-body p {{
    font-size: 15px;
    color: var(--text-secondary);
    margin-bottom: 12px;
    line-height: 1.7;
  }}
  .section-body p:last-child {{ margin-bottom: 0; }}
  .section-body ul {{
    margin: 8px 0 12px 20px;
    color: var(--text-secondary);
  }}
  .section-body li {{
    font-size: 15px;
    margin-bottom: 6px;
    line-height: 1.6;
  }}
  .section-body strong {{ color: var(--text-primary); font-weight: 600; }}
  .section-body em {{ color: var(--text-secondary); }}
  .section-body code {{
    font-family: var(--font-mono);
    font-size: 13px;
    background: var(--surface-2);
    padding: 1px 5px;
    border-radius: 3px;
  }}
  .section-body hr {{
    border: none;
    border-top: 1px solid var(--border);
    margin: 16px 0;
  }}
  .section-body p:empty {{ margin-bottom: 4px; }}

  /* ── Data tables (from agent Markdown tables) ── */
  .data-table {{
    width: 100%;
    border-collapse: collapse;
    margin: 16px 0 20px;
    font-family: var(--font-ui);
    font-size: 13px;
  }}
  .data-table thead tr {{
    background: var(--surface-2);
    border-bottom: 2px solid var(--border);
  }}
  .data-table th {{
    padding: 9px 12px;
    text-align: left;
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.03em;
    font-size: 12px;
    text-transform: uppercase;
  }}
  .data-table td {{
    padding: 9px 12px;
    border-bottom: 1px solid var(--surface-2);
    color: var(--text-primary);
    line-height: 1.5;
    vertical-align: top;
    word-break: break-word;
    max-width: 320px;
  }}
  .data-table td:first-child {{
    font-weight: 600;
    color: var(--text-primary);
    white-space: nowrap;
    max-width: 160px;
  }}
  /* Only apply monospace/blue to cells that look like numeric values */
  .data-table td.numeric {{
    font-family: var(--font-mono);
    font-size: 12px;
    color: var(--accent);
    white-space: nowrap;
  }}
  .data-table tbody tr:hover {{
    background: var(--surface-2);
  }}
  .data-table tbody tr:last-child td {{
    border-bottom: none;
  }}
  /* Tables inside debate columns */
  .debate-side .data-table th {{
    font-size: 11px;
  }}
  .debate-side .data-table td {{
    font-size: 13px;
    padding: 7px 10px;
  }}

  /* ── Full decision section ── */
  .decision-body {{
    font-family: var(--font-body);
    font-size: 16px;
    line-height: 1.75;
    color: var(--text-primary);
  }}
  .decision-body p {{ margin-bottom: 14px; }}
  .decision-body strong {{ color: var(--text-primary); font-weight: 600; }}

  /* ── Debate columns ── */
  .debate-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 24px;
    margin-top: 4px;
  }}
  .debate-side {{
    padding: 20px;
    border-radius: 4px;
    font-size: 14px;
    line-height: 1.65;
  }}
  .debate-side.bull {{
    background: var(--bullish-bg);
    border: 1px solid #b8dfc8;
  }}
  .debate-side.bear {{
    background: var(--bearish-bg);
    border: 1px solid #e8b4b4;
  }}
  .debate-label {{
    font-family: var(--font-ui);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 12px;
  }}
  .bull .debate-label {{ color: var(--bullish); }}
  .bear .debate-label {{ color: var(--bearish); }}
  .debate-side p {{ color: var(--text-secondary); margin-bottom: 8px; font-size: 14px; }}
  .debate-side ul {{ margin-left: 16px; color: var(--text-secondary); }}
  .debate-side li {{ font-size: 14px; margin-bottom: 5px; }}

  /* ── Footer / disclaimer ── */
  .report-footer {{
    padding: 24px 56px;
    background: var(--surface-2);
    border-top: 1px solid var(--border);
  }}
  .disclaimer {{
    font-family: var(--font-ui);
    font-size: 11px;
    color: var(--text-tertiary);
    line-height: 1.6;
  }}
  .disclaimer strong {{ color: var(--text-secondary); }}

  /* ── Print / PDF ── */
  @media print {{
    body {{ background: white; }}
    .report {{
      max-width: none;
      border: none;
    }}
    section {{ break-inside: avoid; }}
    .debate-grid {{ break-inside: avoid; }}
  }}
</style>
</head>
<body>
<div class="report">

  <!-- Header -->
  <header class="report-header">
    <p class="report-brand">AI Analyst Weekly &nbsp;·&nbsp; Research Report</p>
    <h1 class="report-ticker">{ticker}</h1>
    <p class="report-meta">Analysis date: {trade_date} &nbsp;·&nbsp; Generated by 8 specialized AI analysts</p>

    <!-- Verdict -->
    <div class="verdict-block {verdict_class}">
      <span class="verdict-badge">{verdict_label}</span>
      <span class="verdict-summary">{_inline_md((state.final_decision or '').split(chr(10))[0])}</span>
    </div>
  </header>

  <!-- Full Decision -->
  <section>
    <h2>Investment Decision</h2>
    <div class="section-rule"></div>
    <div class="decision-body">
      {_md_to_html(state.final_decision)}
    </div>
  </section>

  <!-- Research Manager Plan -->
  {section("Research Manager Summary", state.investment_plan)}

  <!-- Trader Proposal -->
  {section("Trader Proposal", state.trader_proposal)}

  <!-- Bull vs Bear -->
  <section>
    <h2>Bull vs. Bear Debate</h2>
    <div class="section-rule"></div>
    <div class="debate-grid">
      {debate_html}
    </div>
  </section>

  <!-- Analyst Reports -->
  {section("Fundamental Analysis", state.fundamentals_report)}
  {section("Technical Analysis", state.market_report)}
  {section("News &amp; Macro", state.news_report)}
  {section("Sentiment Analysis", state.sentiment_report)}

  <!-- Footer -->
  <footer class="report-footer">
    <p class="disclaimer">
      <strong>Educational research only. Not investment advice.</strong>
      This report is generated by artificial intelligence for informational purposes only.
      Nothing here constitutes a recommendation to buy, sell, or hold any security.
      AI systems can produce errors, hallucinations, and reflect biases in training data.
      Past analysis accuracy does not predict future results.
      Always consult a licensed financial advisor before making investment decisions.
      AI Analyst Weekly is not a registered investment adviser.
    </p>
  </footer>

</div>
</body>
</html>"""


# ── PDF via Playwright ────────────────────────────────────────────────────────

async def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("  ⚠  playwright not installed — skipping PDF.")
        print("     Run: uv pip install playwright && python -m playwright install chromium")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto(f"file://{html_path.resolve()}", wait_until="networkidle")
        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
        )
        await browser.close()


# ── Main ──────────────────────────────────────────────────────────────────────

async def run(ticker: str, trade_date: str, stem: str, make_pdf: bool) -> None:
    from tradingagents.pipeline.runner import run_analysis

    print(f"\n  AI Analyst Weekly — Report Generator")
    print(f"  {'─' * 38}")
    print(f"  Ticker : {ticker.upper()}")
    print(f"  Date   : {trade_date}")
    print()

    TOTAL = 9
    agents_done: list[str] = []

    async def on_agent_complete(agent_name: str, state) -> None:
        if agent_name not in agents_done:
            agents_done.append(agent_name)
        n = len(agents_done)
        summary = state.agent_summaries.get(agent_name, "")
        note = f"  {summary[:60]}" if summary else ""
        print(f"  [{n}/{TOTAL}] {agent_name}{note}")

    state = await run_analysis(
        ticker=ticker,
        trade_date=trade_date,
        on_agent_complete=on_agent_complete,
    )

    # Build and save HTML
    html = build_html(ticker, trade_date, state)
    out = Path(stem)
    out.parent.mkdir(parents=True, exist_ok=True)
    html_path = out.with_suffix(".html")
    html_path.write_text(html, encoding="utf-8")
    print(f"\n  HTML  -> {html_path.resolve()}")

    # Convert to PDF
    if make_pdf:
        pdf_path = out.with_suffix(".pdf")
        print(f"  PDF   -> {pdf_path.resolve()}  (rendering...)", end="", flush=True)
        await html_to_pdf(html_path, pdf_path)
        print(" done")

    # Print verdict
    verdict_line = (state.final_decision or "").split("\n")[0]
    print(f"\n  {verdict_line}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate an AI Analyst Weekly report")
    parser.add_argument("ticker", help="Ticker symbol, e.g. NVDA")
    parser.add_argument("trade_date", nargs="?", default=str(date.today()),
                        help="Analysis date YYYY-MM-DD (default: today)")
    parser.add_argument("--output", "-o", default=None,
                        help="Output path without extension (default: reports/<TICKER>_<DATE>)")
    parser.add_argument("--no-pdf", action="store_true", help="HTML only, skip PDF")
    args = parser.parse_args()

    ticker = args.ticker.upper().strip()
    stem = args.output or f"reports/{ticker}_{args.trade_date}"
    asyncio.run(run(ticker, args.trade_date, stem, make_pdf=not args.no_pdf))


if __name__ == "__main__":
    main()
