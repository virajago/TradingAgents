"""Resend email integration: digest + alert emails."""
import logging
import re

import resend

from saas.config import get_settings

logger = logging.getLogger(__name__)

_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)


async def send_digest_email(to_email: str, html: str, trade_date: str) -> None:
    """Send the weekly digest HTML email via Resend."""
    settings = get_settings()
    resend.api_key = settings.resend_api_key

    title_match = _TITLE_RE.search(html)
    subject = title_match.group(1).strip() if title_match else f"Your Sunday Report — {trade_date}"

    try:
        resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
            }
        )
        logger.info("Digest email sent to %s", to_email)
    except Exception:
        logger.exception("Failed to send digest email to %s", to_email)
        raise


async def send_alert_email(to_email: str, ticker: str, move_pct: float, analysis: str) -> None:
    """Send a red-flag alert email for a significant price move."""
    settings = get_settings()
    resend.api_key = settings.resend_api_key

    direction = "down" if move_pct < 0 else "up"
    direction_label = direction.upper()
    move_abs = abs(move_pct)
    subject = f"⚡ {ticker} {direction} {move_abs:.1f}% — AI rapid analysis"

    # Colour coding: down = red tones, up = green tones
    if move_pct < 0:
        badge_bg, badge_fg = "#fbeaea", "#8b1a1a"
        icon = "&#9660;"  # ▼
    else:
        badge_bg, badge_fg = "#e8f5ee", "#1a6b3c"
        icon = "&#9650;"  # ▲

    analysis_escaped = analysis.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    on_demand_url = f"https://aianalystweekly.com/analyze?ticker={ticker}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f9fafb;
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,
             'Helvetica Neue',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" border="0"
       style="background-color:#f9fafb;padding:40px 16px;">
  <tr>
    <td align="center">
      <table width="560" cellpadding="0" cellspacing="0" border="0"
             style="max-width:560px;width:100%;background-color:#ffffff;
                    border-radius:12px;box-shadow:0 1px 3px rgba(0,0,0,0.08);
                    overflow:hidden;">

        <!-- Alert header -->
        <tr>
          <td style="background-color:#111827;padding:24px 28px;">
            <p style="margin:0;font-size:12px;font-weight:600;letter-spacing:1px;
                       color:#9ca3af;text-transform:uppercase;">AI Analyst Weekly</p>
            <h1 style="margin:6px 0 0;font-size:18px;font-weight:700;color:#ffffff;">
              Red Flag Alert
            </h1>
          </td>
        </tr>

        <!-- Alert body -->
        <tr>
          <td style="padding:28px;">

            <!-- Ticker + move badge -->
            <table width="100%" cellpadding="0" cellspacing="0" border="0"
                   style="margin-bottom:20px;">
              <tr>
                <td>
                  <span style="font-size:28px;font-weight:800;color:#111827;
                               letter-spacing:-0.5px;">{ticker}</span>
                </td>
                <td style="text-align:right;vertical-align:middle;">
                  <span style="display:inline-block;padding:6px 14px;border-radius:6px;
                               font-size:16px;font-weight:800;
                               background-color:{badge_bg};color:{badge_fg};">
                    {icon} {move_abs:.1f}% {direction_label}
                  </span>
                </td>
              </tr>
            </table>

            <!-- Analysis text -->
            <div style="background-color:#f9fafb;border-radius:8px;
                        padding:16px 20px;margin-bottom:20px;">
              <p style="margin:0;font-size:14px;line-height:1.7;color:#374151;">
                {analysis_escaped}
              </p>
            </div>

            <!-- CTA -->
            <table cellpadding="0" cellspacing="0" border="0">
              <tr>
                <td style="border-radius:6px;background-color:#1d4ed8;">
                  <a href="{on_demand_url}"
                     style="display:inline-block;padding:12px 24px;
                            font-size:14px;font-weight:600;color:#ffffff;
                            text-decoration:none;">
                    Run full 8-agent analysis →
                  </a>
                </td>
              </tr>
            </table>

          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="background-color:#f9fafb;padding:16px 28px;
                     border-top:1px solid #e5e7eb;">
            <p style="margin:0;font-size:12px;color:#9ca3af;line-height:1.6;">
              AI Analyst Weekly · {to_email}<br>
              This is an automated alert based on intraday price data.
              Not financial advice.<br>
              <a href="https://aianalystweekly.com/settings/notifications"
                 style="color:#6b7280;text-decoration:underline;">Manage alerts</a>
            </p>
          </td>
        </tr>

      </table>
    </td>
  </tr>
</table>

</body>
</html>"""

    try:
        resend.Emails.send(
            {
                "from": settings.resend_from_email,
                "to": to_email,
                "subject": subject,
                "html": html,
            }
        )
        logger.info("Alert email sent to %s: %s %+.1f%%", to_email, ticker, move_pct)
    except Exception:
        logger.exception("Failed to send alert email to %s", to_email)
        raise
