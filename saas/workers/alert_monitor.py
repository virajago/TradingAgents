"""Polls Finnhub for material price moves on watched tickers. Sends rapid alert emails."""
import logging
import uuid

from supabase import create_client

from saas.config import CREDITS_ALERT, get_settings
from saas.email.sender import send_alert_email

logger = logging.getLogger(__name__)

# A price move of this magnitude (%) triggers an alert
_ALERT_THRESHOLD_PCT = 5.0


async def check_alerts() -> None:
    """
    1. Collect all distinct tickers across active subscribers' watchlists.
    2. Poll Finnhub quote endpoint for each.
    3. If the intraday move exceeds the threshold, send an alert email to
       every subscriber watching that ticker.

    Phase 1A uses a simple percentage-move trigger.
    Phase 1B can add: earnings release detection, major news, unusual volume.
    """
    settings = get_settings()

    if not settings.finnhub_api_key:
        logger.warning("FINNHUB_API_KEY not configured — skipping alert check")
        return

    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)

    # Join watchlist_items → profiles to get only active subscribers
    result = (
        supabase.table("watchlist_items")
        .select("ticker, profiles!inner(id, email, subscription_status)")
        .eq("profiles.subscription_status", "active")
        .execute()
    )

    # Group: ticker → [user dicts]
    ticker_users: dict[str, list[dict]] = {}
    for row in result.data or []:
        ticker = row["ticker"]
        profile = row.get("profiles") or {}
        if not profile:
            continue
        ticker_users.setdefault(ticker, []).append(profile)

    if not ticker_users:
        logger.debug("Alert check: no active watchlist items")
        return

    import finnhub  # local import — not available in test envs without the package

    client = finnhub.Client(api_key=settings.finnhub_api_key)

    for ticker, users in ticker_users.items():
        try:
            quote = client.quote(ticker)
            prev_close = quote.get("pc") or 0
            current = quote.get("c") or 0

            if prev_close == 0:
                logger.debug("Alert check: %s has no previous close — skipping", ticker)
                continue

            pct_change = ((current - prev_close) / prev_close) * 100

            if abs(pct_change) < _ALERT_THRESHOLD_PCT:
                continue

            direction = "down" if pct_change < 0 else "up"
            analysis = (
                f"{ticker} is {direction} {abs(pct_change):.1f}% today "
                f"(current: ${current:.2f}, prev close: ${prev_close:.2f}). "
                "Monitor for continuation or reversal at key levels."
            )

            for user in users:
                try:
                    # Deduct 1 credit per alert; skip if insufficient balance
                    alert_ref = str(uuid.uuid4())
                    deduct_result = supabase.rpc(
                        "deduct_credits",
                        {
                            "p_user_id": user["id"],
                            "p_amount": CREDITS_ALERT,
                            "p_action": "alert",
                            "p_reference_id": alert_ref,
                        },
                    ).execute()
                    if deduct_result.data is None or deduct_result.data < 0:
                        logger.warning(
                            "Alert: insufficient credits for %s / %s — skipping",
                            user["email"],
                            ticker,
                        )
                        continue
                    await send_alert_email(user["email"], ticker, pct_change, analysis)
                    logger.info(
                        "Alert sent: user=%s ticker=%s move=%.1f%%",
                        user["email"],
                        ticker,
                        pct_change,
                    )
                except Exception:
                    logger.exception("Failed to send alert to %s for %s", user["email"], ticker)

        except Exception:
            logger.exception("Alert check failed for %s", ticker)
