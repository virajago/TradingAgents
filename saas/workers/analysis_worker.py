"""Background worker: runs a single TradingAgents analysis for a given user+ticker."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

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
