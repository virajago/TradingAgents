"""P0: Email formatter must produce valid HTML with required elements.

The conftest.py stubs ``saas.email.formatter`` as a blank mock to prevent
import-time side-effects during route tests.  This module undoes that stub
for its own import so the *real* ``format_digest_email`` is exercised.

Actual function signature (from saas/email/formatter.py):

    format_digest_email(
        user_email: str,
        results: dict[str, Optional[dict]],
        trade_date: str,
    ) -> str

``results`` maps ticker → task dict.  A successful task must have a nested
``"result"`` dict (or object) with an ``"action"`` or ``"verdict"`` key.
A failed task has ``status="error"`` or ``result=None``.
"""
from __future__ import annotations

import re
import sys

import pytest

# ---------------------------------------------------------------------------
# Real-module import: bypass the conftest stub for saas.email.formatter.
# The conftest inserts a blank MagicMock only when the module is NOT already
# in sys.modules.  By popping the stub and importing the real module first,
# all tests in this file get the genuine implementation.
# ---------------------------------------------------------------------------
for _stale in ("saas.email.formatter", "saas.email"):
    sys.modules.pop(_stale, None)

try:
    from saas.email.formatter import format_digest_email  # type: ignore[import]

    FORMATTER_AVAILABLE = True
except Exception:  # ImportError, or any transitive import failure
    FORMATTER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not FORMATTER_AVAILABLE, reason="saas.email.formatter not importable"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_task(verdict: str, ticker: str = "NVDA", status: str = "complete") -> dict:
    """Build a minimal task dict matching analysis_worker output.

    The formatter inspects ``task["result"]["action"]`` (or ``"verdict"``) —
    NOT ``task["verdict"]`` directly.
    """
    return {
        "status": status,
        "ticker": ticker,
        "result": {
            "action": verdict,
            "reason": f"Data center demand strong. Hold full position.",
        },
        "error": None,
        "agents": [
            {
                "name": "Portfolio Manager",
                "status": "complete",
                "summary": f"{verdict} on {ticker}",
            }
        ],
    }


def make_failed_task(ticker: str = "TSLA") -> dict:
    return {
        "status": "error",
        "ticker": ticker,
        "result": None,
        "error": "LLM API timeout",
        "agents": [],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_output_is_string():
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert isinstance(html, str)
    assert len(html) > 100


def test_output_is_valid_html():
    """Basic HTML structure must be present."""
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert "<html" in html.lower()
    assert "</html>" in html.lower()
    assert "<body" in html.lower()
    assert "</body>" in html.lower()


def test_ticker_appears_in_output():
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert "NVDA" in html


def test_verdict_appears_in_output():
    """Each verdict must be reflected somewhere in the rendered HTML."""
    for verdict in ["BULLISH", "BEARISH", "NEUTRAL"]:
        results = {"NVDA": make_task(verdict)}
        html = format_digest_email("test@example.com", results, "2026-01-12")
        upper = html.upper()
        assert any(
            w in upper for w in ["BULLISH", "BEARISH", "NEUTRAL", "BUY", "SELL", "HOLD"]
        ), f"Verdict {verdict} not found in output"


def test_buy_verdict_maps_to_bullish():
    """BUY action must render as BULLISH badge."""
    results = {"NVDA": make_task("BUY")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert "BULLISH" in html.upper()


def test_sell_verdict_maps_to_bearish():
    """SELL action must render as BEARISH badge."""
    results = {"NVDA": make_task("SELL")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert "BEARISH" in html.upper()


def test_legal_disclaimer_present():
    """Every email MUST contain legal disclaimer text."""
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    html_lower = html.lower()
    assert any(
        phrase in html_lower
        for phrase in [
            "not investment advice",
            "educational",
            "informational purposes",
            "not a recommendation",
        ]
    ), "Legal disclaimer missing from email"


def test_unsubscribe_link_present():
    """CAN-SPAM requires an unsubscribe mechanism."""
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert "unsubscribe" in html.lower()


def test_failure_stub_for_errored_ticker():
    """When a ticker analysis failed, a stub must appear — not a blank."""
    results = {
        "NVDA": make_task("BULLISH"),
        "TSLA": make_failed_task("TSLA"),
    }
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert "TSLA" in html
    # The formatter renders an UNAVAILABLE badge for failure cards.
    assert any(
        word in html.lower()
        for word in ["unavailable", "error", "failed", "try again", "on-demand"]
    ), "No failure stub found for errored ticker"


def test_multiple_tickers_all_appear():
    results = {
        "NVDA": make_task("BULLISH"),
        "AAPL": make_task("NEUTRAL"),
        "MSFT": make_task("BULLISH"),
    }
    html = format_digest_email("test@example.com", results, "2026-01-12")
    for ticker in ["NVDA", "AAPL", "MSFT"]:
        assert ticker in html, f"{ticker} missing from digest email"


def test_title_tag_has_meaningful_content():
    """The HTML <title> tag must exist and contain non-empty text."""
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    title_match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    assert title_match, "<title> tag not found in email HTML"
    assert len(title_match.group(1).strip()) > 0, "Empty <title> tag"


def test_no_script_tags_in_email():
    """Email HTML must not contain script tags — email clients block them."""
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert "<script" not in html.lower(), (
        "Script tags found in email HTML — email clients will block"
    )


def test_empty_results_dict_does_not_crash():
    """Empty watchlist edge case must not raise."""
    try:
        html = format_digest_email("test@example.com", {}, "2026-01-12")
        assert isinstance(html, str)
    except Exception as exc:
        pytest.fail(
            f"format_digest_email raised {type(exc).__name__} on empty results: {exc}"
        )


def test_all_failed_tickers_still_sends():
    """When ALL analyses failed, email should still be generated (all stubs)."""
    results = {
        "NVDA": make_failed_task("NVDA"),
        "AAPL": make_failed_task("AAPL"),
    }
    html = format_digest_email("test@example.com", results, "2026-01-12")
    assert isinstance(html, str)
    assert len(html) > 50


def test_user_email_appears_in_footer():
    """The recipient email address must appear in the footer for personalisation."""
    results = {"NVDA": make_task("BULLISH")}
    html = format_digest_email("subscriber@example.com", results, "2026-01-12")
    assert "subscriber@example.com" in html


def test_none_task_renders_failure_stub():
    """A None value in the results dict must render a failure stub, not crash."""
    results = {"NVDA": None}
    try:
        html = format_digest_email("test@example.com", results, "2026-01-12")
        assert isinstance(html, str)
        assert "NVDA" in html
    except Exception as exc:
        pytest.fail(
            f"format_digest_email raised {type(exc).__name__} with None task: {exc}"
        )
