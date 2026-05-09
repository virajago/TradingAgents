"""
Convert TradingAgents analysis results into a production-quality HTML digest email.

Design decisions:
- Table-based layout for Outlook compatibility
- Inline CSS only (no external stylesheets)
- Verdict badges: BULLISH (#1a6b3c on #e8f5ee), BEARISH (#8b1a1a on #fbeaea), NEUTRAL (#555 on #f0f0f0)
- Clean editorial style with generous whitespace
- Failure stub for errored / missing analyses
"""
from __future__ import annotations

import html as html_lib
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Colour tokens
# ---------------------------------------------------------------------------

_BADGE = {
    "BULLISH": ("background-color:#e8f5ee;color:#1a6b3c;", "BULLISH"),
    "BEARISH": ("background-color:#fbeaea;color:#8b1a1a;", "BEARISH"),
    "NEUTRAL": ("background-color:#f0f0f0;color:#555555;", "NEUTRAL"),
}

_CONVICTION_COLOUR = {
    "High": "#1a6b3c",
    "Moderate": "#b45309",
    "Low": "#6b7280",
}

_BASE_URL = "https://aianalystweekly.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _esc(text: str) -> str:
    """HTML-escape a string."""
    return html_lib.escape(str(text))


def _badge(verdict: str) -> str:
    style, label = _BADGE.get(verdict.upper(), _BADGE["NEUTRAL"])
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:4px;'
        f'font-size:12px;font-weight:700;letter-spacing:0.5px;{style}">'
        f"{label}</span>"
    )


def _ticker_card(ticker: str, task: Optional[dict]) -> str:
    """Render a single ticker analysis as a table card."""
    if task is None or task.get("status") == "error" or task.get("result") is None:
        return _failure_card(ticker)
    return _success_card(ticker, task)


def _success_card(ticker: str, task: dict) -> str:
    result = task.get("result") or {}

    # TradingAgentsGraph returns the PortfolioDecision object or dict.
    # Normalise to dict.
    if hasattr(result, "__dict__"):
        result = result.__dict__

    verdict_raw = str(result.get("action", result.get("verdict", "NEUTRAL"))).upper()
    # Map BUY/SELL → BULLISH/BEARISH for display
    if verdict_raw in ("BUY",):
        verdict = "BULLISH"
    elif verdict_raw in ("SELL",):
        verdict = "BEARISH"
    elif verdict_raw in ("HOLD",):
        verdict = "NEUTRAL"
    else:
        verdict = verdict_raw if verdict_raw in _BADGE else "NEUTRAL"

    conviction = str(result.get("conviction", "")).strip()
    conviction_pct = result.get("conviction_pct") or result.get("confidence")
    summary = str(result.get("reason", result.get("summary", result.get("reasoning", "")))).strip()

    conviction_colour = _CONVICTION_COLOUR.get(conviction, "#6b7280")

    conviction_html = ""
    if conviction:
        pct_text = f" ({conviction_pct}%)" if conviction_pct is not None else ""
        conviction_html = (
            f'<span style="color:{conviction_colour};font-weight:600;">'
            f"{_esc(conviction)}{_esc(pct_text)}</span>"
        )

    summary_html = ""
    if summary:
        summary_html = (
            f'<p style="margin:12px 0 0;font-size:14px;line-height:1.6;'
            f'color:#374151;">{_esc(summary[:600])}{"…" if len(summary) > 600 else ""}</p>'
        )

    on_demand_url = f"{_BASE_URL}/analyze?ticker={_esc(ticker)}"

    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="border:1px solid #e5e7eb;border-radius:8px;margin-bottom:20px;overflow:hidden;">
  <tr>
    <td style="padding:20px 24px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="vertical-align:middle;">
            <span style="font-size:20px;font-weight:700;color:#111827;
                         letter-spacing:-0.3px;">{_esc(ticker)}</span>
          </td>
          <td style="text-align:right;vertical-align:middle;">
            {_badge(verdict)}
            {"&nbsp;&nbsp;" + conviction_html if conviction_html else ""}
          </td>
        </tr>
      </table>
      {summary_html}
      <p style="margin:14px 0 0;font-size:13px;">
        <a href="{on_demand_url}" style="color:#1d4ed8;text-decoration:none;
           font-weight:500;">View full analysis →</a>
      </p>
    </td>
  </tr>
</table>
"""


def _failure_card(ticker: str) -> str:
    on_demand_url = f"{_BASE_URL}/analyze?ticker={_esc(ticker)}"
    return f"""
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="border:1px solid #e5e7eb;border-radius:8px;margin-bottom:20px;
              background-color:#fafafa;overflow:hidden;">
  <tr>
    <td style="padding:20px 24px 16px;">
      <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
          <td style="vertical-align:middle;">
            <span style="font-size:20px;font-weight:700;color:#6b7280;
                         letter-spacing:-0.3px;">{_esc(ticker)}</span>
          </td>
          <td style="text-align:right;vertical-align:middle;">
            <span style="display:inline-block;padding:3px 10px;border-radius:4px;
                         font-size:12px;font-weight:700;letter-spacing:0.5px;
                         background-color:#f3f4f6;color:#9ca3af;">UNAVAILABLE</span>
          </td>
        </tr>
      </table>
      <p style="margin:10px 0 0;font-size:14px;color:#6b7280;">
        Analysis unavailable this week.
        <a href="{on_demand_url}"
           style="color:#1d4ed8;text-decoration:none;font-weight:500;">
          Run on-demand →</a>
      </p>
    </td>
  </tr>
</table>
"""


def _build_subject(results: dict[str, Optional[dict]]) -> str:
    """Build email subject line from results dict."""
    parts = []
    for ticker, task in results.items():
        if task and task.get("status") == "complete" and task.get("result"):
            result = task["result"]
            if hasattr(result, "__dict__"):
                result = result.__dict__
            action = str(result.get("action", result.get("verdict", "NEUTRAL"))).upper()
            if action in ("BUY",):
                label = "Bullish"
            elif action in ("SELL",):
                label = "Bearish"
            elif action in ("HOLD",):
                label = "Neutral"
            elif action in _BADGE:
                label = action.capitalize()
            else:
                label = "Neutral"
            parts.append(f"{ticker} {label}")

    if not parts:
        return "Your Sunday AI Analyst Report"

    if len(parts) <= 3:
        return f"Your Sunday Report: {', '.join(parts)}"

    preview = ", ".join(parts[:2])
    return f"Your Sunday Report: {preview}, +{len(parts) - 2} more"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def format_digest_email(
    user_email: str,
    results: dict[str, Optional[dict]],
    trade_date: str,
) -> str:
    """
    Convert analysis results dict into a complete HTML email string.

    Args:
        user_email: Recipient email address (used for personalisation).
        results: Mapping of ticker → task dict (from analysis_worker) or None.
        trade_date: ISO date string (YYYY-MM-DD) for the analysis run date.

    Returns:
        Complete HTML string ready to pass to Resend.
    """
    subject = _build_subject(results)

    # Format date for display: "Sunday, May 4, 2025"
    try:
        dt = datetime.fromisoformat(trade_date)
        display_date = dt.strftime("%A, %B %-d, %Y")
    except ValueError:
        display_date = trade_date

    # Tally verdict counts for the header
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    for task in results.values():
        if not task or task.get("status") != "complete" or not task.get("result"):
            continue
        r = task["result"]
        if hasattr(r, "__dict__"):
            r = r.__dict__
        action = str(r.get("action", r.get("verdict", "NEUTRAL"))).upper()
        if action in ("BUY", "BULLISH"):
            bullish_count += 1
        elif action in ("SELL", "BEARISH"):
            bearish_count += 1
        else:
            neutral_count += 1

    # Build ticker cards
    cards_html = "\n".join(_ticker_card(ticker, task) for ticker, task in results.items())

    total = len(results)
    plural = "ticker" if total == 1 else "tickers"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{_esc(subject)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,
             'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

<!-- Outer wrapper -->
<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:#f9fafb;padding:40px 16px;">
  <tr>
    <td align="center">

      <!-- Email card -->
      <table width="600" cellpadding="0" cellspacing="0" border="0"
             style="max-width:600px;width:100%;background-color:#ffffff;
                    border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);
                    overflow:hidden;">

        <!-- Header bar -->
        <tr>
          <td style="background-color:#111827;padding:28px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td>
                  <p style="margin:0;font-size:13px;font-weight:600;letter-spacing:1px;
                             color:#9ca3af;text-transform:uppercase;">AI Analyst Weekly</p>
                  <h1 style="margin:6px 0 0;font-size:22px;font-weight:700;color:#ffffff;
                              letter-spacing:-0.5px;">Your Weekly Report</h1>
                  <p style="margin:4px 0 0;font-size:14px;color:#6b7280;">{_esc(display_date)}</p>
                </td>
                <td style="text-align:right;vertical-align:top;">
                  <!-- Verdict tally pills -->
                  <table cellpadding="0" cellspacing="4" border="0" style="display:inline-table;">
                    <tr>
                      {"<td><span style='display:inline-block;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:700;background-color:#e8f5ee;color:#1a6b3c;'>" + str(bullish_count) + " Bullish</span></td>" if bullish_count else ""}
                      {"<td><span style='display:inline-block;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:700;background-color:#fbeaea;color:#8b1a1a;'>" + str(bearish_count) + " Bearish</span></td>" if bearish_count else ""}
                      {"<td><span style='display:inline-block;padding:4px 10px;border-radius:20px;font-size:12px;font-weight:700;background-color:#f0f0f0;color:#555;'>" + str(neutral_count) + " Neutral</span></td>" if neutral_count else ""}
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:28px 32px 8px;">
            <p style="margin:0 0 20px;font-size:14px;color:#6b7280;">
              Your 8-agent AI team analysed {total} {plural} this week.
              Here's what they found.
            </p>

            <!-- Ticker cards -->
            {cards_html}
          </td>
        </tr>

        <!-- Divider -->
        <tr>
          <td style="padding:0 32px;">
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:0;">
          </td>
        </tr>

        <!-- CTA row -->
        <tr>
          <td style="padding:20px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td>
                  <p style="margin:0;font-size:13px;color:#6b7280;">
                    Want more depth?
                    <a href="{_BASE_URL}/analyze"
                       style="color:#1d4ed8;text-decoration:none;font-weight:500;">
                      Run on-demand analysis →</a>
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background-color:#f9fafb;padding:20px 32px;border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
              AI Analyst Weekly · {_esc(user_email)}<br>
              Analysis is for informational purposes only and does not constitute
              financial advice.<br>
              <a href="{_BASE_URL}/settings/notifications"
                 style="color:#6b7280;text-decoration:underline;">Manage notifications</a>
              &nbsp;·&nbsp;
              <a href="{_BASE_URL}/unsubscribe"
                 style="color:#6b7280;text-decoration:underline;">Unsubscribe</a>
            </p>
          </td>
        </tr>

      </table>
      <!-- /Email card -->

    </td>
  </tr>
</table>
<!-- /Outer wrapper -->

</body>
</html>"""
