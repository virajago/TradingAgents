"""Batch scheduler: runs weekly analyses for all users' watchlist tickers."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, Optional

from supabase import create_client

from saas.config.settings import get_settings
from saas.workers.analysis_worker import run_analysis, _fetch_portfolio_context

logger = logging.getLogger(__name__)


def run_weekly_batch(trade_date: Optional[str] = None) -> None:
    """Run weekly analyses for all active users.

    Fetches each user's watchlist tickers and portfolio holdings once per user,
    then delegates to run_analysis() for each ticker.

    Args:
        trade_date: ISO date string to analyse. Defaults to today.
    """
    if trade_date is None:
        trade_date = date.today().isoformat()

    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    # Fetch all active users (profiles table is used as the user registry)
    users_result = supabase.table("profiles").select("id").execute()
    users = users_result.data or []

    logger.info("Running weekly batch for %d users on %s", len(users), trade_date)

    for user_row in users:
        user_id = user_row["id"]
        try:
            _run_user_batch(supabase, user_id, trade_date)
        except Exception as exc:
            logger.error("Batch failed for user %s: %s", user_id, exc, exc_info=True)


def _run_user_batch(supabase, user_id: str, trade_date: str) -> None:
    """Run analyses for a single user across all their watched tickers."""
    # Fetch portfolio holdings once per user (re-used for all their tickers)
    portfolio_context = _fetch_portfolio_context(supabase, user_id)

    # Fetch watchlist tickers — assumes a watchlist table; adapt as needed
    try:
        watchlist_result = supabase.table("watchlist").select("ticker").eq(
            "user_id", user_id
        ).execute()
        tickers = [row["ticker"] for row in (watchlist_result.data or [])]
    except Exception as exc:
        logger.warning("Could not fetch watchlist for user %s: %s", user_id, exc)
        return

    if not tickers:
        logger.debug("No watchlist tickers for user %s", user_id)
        return

    logger.info("Batch: user=%s tickers=%s date=%s", user_id, tickers, trade_date)

    for ticker in tickers:
        try:
            run_analysis(
                user_id=user_id,
                ticker=ticker,
                trade_date=trade_date,
                portfolio_context=portfolio_context,
            )
        except Exception as exc:
            logger.error(
                "Analysis failed: user=%s ticker=%s date=%s error=%s",
                user_id, ticker, trade_date, exc,
                exc_info=True,
            )
