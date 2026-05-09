"""Sunday 8pm ET batch runner. Triggered by Cloud Scheduler via POST /internal/batch/run."""
import asyncio
import logging
import uuid
from datetime import date

from supabase import create_client

from saas.config import CREDITS_WEEKLY_DIGEST_PER_TICKER, get_settings
from saas.email.formatter import format_digest_email
from saas.email.sender import send_digest_email
from saas.workers.analysis_worker import get_task, run_analysis

logger = logging.getLogger(__name__)


async def run_weekly_batch() -> dict:
    """
    Main Sunday batch entry point.

    1. Query all active subscribers and their watchlists.
    2. Run TradingAgents analysis for every (user, ticker) pair in parallel,
       bounded by the global Semaphore in analysis_worker.
    3. Format per-user HTML digest from the results.
    4. Send via Resend.

    Returns summary: {users_processed, analyses_run, emails_sent, errors}
    """
    settings = get_settings()
    supabase = create_client(settings.supabase_url, settings.supabase_service_role_key)
    trade_date = date.today().isoformat()

    # 1. Fetch active subscribers with their watchlists in a single query
    result = (
        supabase.table("profiles")
        .select("id, email, watchlist_items(ticker)")
        .eq("subscription_status", "active")
        .execute()
    )
    users = result.data or []
    logger.info("Batch starting: %d active subscribers", len(users))

    stats: dict = {
        "users_processed": 0,
        "analyses_run": 0,
        "emails_sent": 0,
        "errors": [],
    }

    # 2. Build (user_id, email, ticker, task_id) tuples for all work items.
    #    Deduct weekly_digest credits per ticker before queuing the analysis so
    #    users with no balance are skipped rather than run for free.
    work_items: list[tuple[str, str, str, str]] = []
    for user in users:
        tickers = [item["ticker"] for item in (user.get("watchlist_items") or [])]
        for ticker in tickers:
            task_id = str(uuid.uuid4())
            # Attempt credit deduction — skip this ticker if insufficient balance
            try:
                result = supabase.rpc(
                    "deduct_credits",
                    {
                        "p_user_id": user["id"],
                        "p_amount": CREDITS_WEEKLY_DIGEST_PER_TICKER,
                        "p_action": "weekly_digest",
                        "p_reference_id": task_id,
                    },
                ).execute()
                if result.data is None or result.data < 0:
                    logger.warning(
                        "Batch: insufficient credits for %s / %s — skipping",
                        user["email"],
                        ticker,
                    )
                    continue
            except Exception:
                logger.exception(
                    "Batch: credit deduction failed for %s / %s — skipping",
                    user["email"],
                    ticker,
                )
                continue
            work_items.append((user["id"], user["email"], ticker, task_id))

    if not work_items:
        logger.info("Batch: no watchlist items found — nothing to do")
        return stats

    # Run all analyses concurrently (Semaphore in analysis_worker caps parallelism)
    await asyncio.gather(
        *[
            run_analysis(
                task_id=task_id,
                ticker=ticker,
                user_id=user_id,
                trade_date=trade_date,
            )
            for user_id, _email, ticker, task_id in work_items
        ],
        return_exceptions=True,
    )
    stats["analyses_run"] = len(work_items)
    logger.info("Batch: %d analyses finished", len(work_items))

    # 3. Group results by user and send digest emails
    user_map: dict[str, dict] = {u["id"]: u for u in users}

    for user_id, user in user_map.items():
        user_tickers_tasks = [
            (ticker, task_id)
            for uid, _email, ticker, task_id in work_items
            if uid == user_id
        ]
        if not user_tickers_tasks:
            continue

        results: dict[str, dict | None] = {
            ticker: get_task(task_id) for ticker, task_id in user_tickers_tasks
        }

        try:
            html = format_digest_email(user["email"], results, trade_date)
            await send_digest_email(user["email"], html, trade_date)
            stats["emails_sent"] += 1
            logger.info("Digest sent to %s (%d tickers)", user["email"], len(results))
        except Exception as exc:
            msg = f"{user['email']}: {exc}"
            stats["errors"].append(msg)
            logger.error("Email failed for %s: %s", user["email"], exc)

        stats["users_processed"] += 1

    logger.info("Batch complete: %s", stats)
    return stats
