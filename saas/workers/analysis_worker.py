"""Background worker: runs a single TradingAgents analysis for a given user+ticker."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

import yfinance as yf
from supabase import create_client

from saas.config.settings import get_settings
from tradingagents.graph.trading_graph import TradingAgentsGraph

logger = logging.getLogger(__name__)


def run_analysis(
    user_id: str,
    ticker: str,
    trade_date: str,
    config: Optional[Dict[str, Any]] = None,
    portfolio_context: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Run a TradingAgents analysis for a single user+ticker.

    Args:
        user_id: Supabase user UUID string.
        ticker: Stock ticker symbol (e.g. "NVDA").
        trade_date: ISO date string (e.g. "2025-01-15").
        config: Optional TradingAgentsGraph config overrides.
        portfolio_context: Pre-fetched holdings dict {TICKER: {shares, avg_cost_usd}}.
            When None, this function fetches holdings from Postgres.

    Returns:
        Dict with "final_state" and "signal" keys.
    """
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    effective_config: Dict[str, Any] = dict(config or {})

    # Fetch portfolio holdings when not pre-fetched by the caller (e.g. single on-demand runs).
    if portfolio_context is None:
        portfolio_context = _fetch_portfolio_context(supabase, user_id)

    if portfolio_context:
        effective_config["portfolio_context"] = portfolio_context

    ta = TradingAgentsGraph(
        debug=False,
        config=effective_config if effective_config else None,
        user_id=user_id,
        supabase_client=supabase,
    )

    logger.info("Starting analysis: user=%s ticker=%s date=%s", user_id, ticker, trade_date)
    final_state, signal = ta.propagate(ticker, trade_date)
    logger.info(
        "Completed analysis: user=%s ticker=%s signal=%s", user_id, ticker, signal
    )

    # Log verdict to the track-record table and fire lifecycle events (non-fatal)
    _log_verdict(supabase, user_id, ticker, trade_date, signal)

    return {"final_state": final_state, "signal": signal}


def _fetch_portfolio_context(supabase, user_id: str) -> Dict[str, Dict[str, Any]]:
    """Fetch portfolio holdings for the user and return them as a context dict."""
    try:
        result = supabase.table("portfolio_holdings").select(
            "ticker,shares,avg_cost_usd"
        ).eq("user_id", user_id).execute()
        return {
            row["ticker"]: {
                "shares": row["shares"],
                "avg_cost_usd": float(row["avg_cost_usd"]),
            }
            for row in (result.data or [])
        }
    except Exception as exc:
        logger.warning("Could not fetch portfolio holdings for user %s: %s", user_id, exc)
        return {}


# ---------------------------------------------------------------------------
# Verdict logging and lifecycle events (non-fatal side effects)
# ---------------------------------------------------------------------------

_VERDICT_MAP: Dict[str, str] = {"BUY": "BULLISH", "SELL": "BEARISH", "HOLD": "NEUTRAL"}


def _log_verdict(supabase, user_id: str, ticker: str, trade_date: str, signal: Any) -> None:
    """
    Log the analysis verdict to the verdicts table and fire Loops lifecycle events.
    Errors here are non-fatal — the analysis result is still returned to the caller.
    """
    try:
        decision_str = str(signal).strip().upper()
        verdict_str = "NEUTRAL"
        for prefix, mapped in _VERDICT_MAP.items():
            if decision_str.startswith(prefix):
                verdict_str = mapped
                break

        # Fetch current prices for the verdict snapshot
        current_price: Optional[float] = None
        spx_price: Optional[float] = None
        try:
            ticker_info = yf.Ticker(ticker).info
            spx_info = yf.Ticker("^GSPC").info
            current_price = ticker_info.get("currentPrice") or ticker_info.get("regularMarketPrice")
            spx_price = spx_info.get("regularMarketPrice")
        except Exception as price_exc:
            logger.warning("Price fetch failed for verdict snapshot ticker=%s: %s", ticker, price_exc)

        supabase.table("verdicts").insert({
            "user_id": user_id,
            "ticker": ticker.upper(),
            "verdict_date": trade_date,
            "verdict": verdict_str,
            "price_at_verdict": current_price,
            "spx_price_at_verdict": spx_price,
        }).execute()

        # Check if this is the user's first completed analysis
        count_result = (
            supabase.table("analyses")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .execute()
        )
        if getattr(count_result, "count", None) == 1:
            profile = (
                supabase.table("profiles")
                .select("email")
                .eq("id", user_id)
                .execute()
            )
            if profile.data and profile.data[0].get("email"):
                import asyncio
                from saas.email.lifecycle import track_event
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(track_event(
                        profile.data[0]["email"],
                        "first_analysis_done",
                        {"ticker": ticker.upper(), "verdict": verdict_str},
                    ))
                except RuntimeError:
                    # No running event loop (synchronous caller) — skip the async event
                    logger.debug("No running event loop; skipping first_analysis_done Loops event")

    except Exception as exc:
        logger.warning("Failed to log verdict for ticker=%s user=%s: %s", ticker, user_id, exc)
