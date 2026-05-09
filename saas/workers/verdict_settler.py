"""
Verdict settlement cron — runs daily, settles 30d and 90d outcomes.
Triggered by Cloud Scheduler via POST /internal/verdicts/settle.
Fetches historical prices from Yahoo Finance and updates settlement fields.
"""
import logging
from datetime import date, timedelta

import yfinance as yf
from supabase import create_client

from saas.config import get_settings

logger = logging.getLogger(__name__)


def _get_close_price(ticker: str, target_date: date) -> float | None:
    """
    Fetch the closing price for a ticker on or near the target date.
    Looks up to 5 days forward to handle weekends and market holidays.
    Returns None if price data is unavailable.
    """
    try:
        start = target_date
        end = target_date + timedelta(days=5)
        hist = yf.download(
            ticker,
            start=start.isoformat(),
            end=end.isoformat(),
            progress=False,
            auto_adjust=True,
        )
        if hist.empty:
            return None
        return round(float(hist["Close"].iloc[0]), 2)
    except Exception:
        logger.exception("Price fetch failed for %s on %s", ticker, target_date)
        return None


async def settle_verdicts() -> dict:
    """
    Find verdicts due for 30d or 90d settlement and settle them.

    A verdict is due for 30d settlement when:
      verdict_date <= today - 30 days AND settled_30d is false.

    A verdict is due for 90d settlement when:
      verdict_date <= today - 90 days AND settled_90d is false.
    """
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    today = date.today()
    cutoff_30d = today - timedelta(days=30)
    cutoff_90d = today - timedelta(days=90)

    stats: dict = {"settled_30d": 0, "settled_90d": 0, "errors": 0}

    # --- 30d settlements due (includes verdicts also due for 90d) ---
    result_30 = (
        supabase.table("verdicts")
        .select("*")
        .eq("settled_30d", False)
        .lte("verdict_date", cutoff_30d.isoformat())
        .execute()
    )

    for verdict in result_30.data or []:
        try:
            ticker = verdict["ticker"]
            verdict_date = date.fromisoformat(verdict["verdict_date"])

            settlement_date_30 = verdict_date + timedelta(days=30)
            price_30d = _get_close_price(ticker, settlement_date_30)
            spx_30d = _get_close_price("^GSPC", settlement_date_30)

            update: dict = {"settled_30d": True}
            if price_30d is not None:
                update["price_30d"] = price_30d
            if spx_30d is not None:
                update["spx_price_30d"] = spx_30d

            # If also past the 90d window and not yet settled, settle both at once
            if verdict_date <= cutoff_90d and not verdict.get("settled_90d"):
                settlement_date_90 = verdict_date + timedelta(days=90)
                price_90d = _get_close_price(ticker, settlement_date_90)
                spx_90d = _get_close_price("^GSPC", settlement_date_90)
                update["settled_90d"] = True
                if price_90d is not None:
                    update["price_90d"] = price_90d
                if spx_90d is not None:
                    update["spx_price_90d"] = spx_90d
                stats["settled_90d"] += 1

            supabase.table("verdicts").update(update).eq("id", verdict["id"]).execute()
            stats["settled_30d"] += 1
            logger.info(
                "Settled 30d: ticker=%s verdict_id=%s price_30d=%s",
                ticker,
                verdict["id"],
                price_30d,
            )

        except Exception:
            stats["errors"] += 1
            logger.exception("Settlement failed for verdict %s", verdict.get("id"))

    # --- 90d-only settlements (30d already done but 90d pending) ---
    result_90 = (
        supabase.table("verdicts")
        .select("*")
        .eq("settled_30d", True)
        .eq("settled_90d", False)
        .lte("verdict_date", cutoff_90d.isoformat())
        .execute()
    )

    for verdict in result_90.data or []:
        try:
            ticker = verdict["ticker"]
            verdict_date = date.fromisoformat(verdict["verdict_date"])
            settlement_date_90 = verdict_date + timedelta(days=90)

            price_90d = _get_close_price(ticker, settlement_date_90)
            spx_90d = _get_close_price("^GSPC", settlement_date_90)

            update = {"settled_90d": True}
            if price_90d is not None:
                update["price_90d"] = price_90d
            if spx_90d is not None:
                update["spx_price_90d"] = spx_90d

            supabase.table("verdicts").update(update).eq("id", verdict["id"]).execute()
            stats["settled_90d"] += 1
            logger.info(
                "Settled 90d: ticker=%s verdict_id=%s price_90d=%s",
                ticker,
                verdict["id"],
                price_90d,
            )

        except Exception:
            stats["errors"] += 1
            logger.exception("90d settlement failed for verdict %s", verdict.get("id"))

    logger.info("Settlement complete: %s", stats)
    return stats
