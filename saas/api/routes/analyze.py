"""Analysis endpoints: submit, poll status, fetch results."""
import asyncio
import logging
import re
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from saas.api.credits import check_and_deduct_credits
from saas.api.deps import get_current_user, get_settings_dep, get_supabase
from saas.config import CREDITS_ON_DEMAND_ANALYSIS, Settings
from saas.workers.analysis_worker import AGENT_NAMES, get_task, run_analysis

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER_RE = re.compile(r"^[A-Z0-9]{1,8}$")


class AnalyzeRequest(BaseModel):
    ticker: str


def _validate_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticker: must be 1-8 uppercase alphanumeric characters",
        )
    return ticker


def _check_rate_limit(
    user_id: str,
    supabase: Client,
    max_per_day: int,
) -> None:
    today = date.today().isoformat()
    result = (
        supabase.table("daily_analysis_counts")
        .select("count")
        .eq("user_id", user_id)
        .eq("date", today)
        .execute()
    )
    current_count = result.data[0]["count"] if result.data else 0
    if current_count >= max_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily limit of {max_per_day} on-demand analyses reached",
        )



@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def submit_analysis(
    body: AnalyzeRequest,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    """
    Submit a ticker for on-demand analysis.

    Returns task_id immediately; poll /analyze/{task_id}/status for progress.
    """
    ticker = _validate_ticker(body.ticker)
    user_id = user["id"]

    # Rate limit check
    _check_rate_limit(user_id, supabase, settings.max_on_demand_per_day)

    # Verify user has active subscription
    profile = (
        supabase.table("profiles")
        .select("subscription_status")
        .eq("id", user_id)
        .execute()
    )
    if not profile.data or profile.data[0]["subscription_status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active subscription required",
        )

    task_id = str(uuid.uuid4())
    trade_date = date.today().isoformat()

    # Atomically check and deduct credits before incurring any LLM cost.
    # Raises HTTP 402 if the user has insufficient credits — task never starts.
    await check_and_deduct_credits(
        user_id=user_id,
        amount=CREDITS_ON_DEMAND_ANALYSIS,
        action="on_demand_analysis",
        reference_id=task_id,
        supabase=supabase,
    )

    # Persist analysis record so we can look it up later
    try:
        supabase.table("analyses").insert(
            {
                "id": task_id,
                "user_id": user_id,
                "ticker": ticker,
                "trade_date": trade_date,
                "source": "on_demand",
                "status": "queued",
            }
        ).execute()
    except Exception:
        logger.exception("Failed to create analysis record for %s / %s", user_id, ticker)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create analysis",
        )

    # Atomic counter increment via SQL function (upsert with increment semantics)
    try:
        supabase.rpc(
            "increment_daily_count",
            {"p_user_id": user_id, "p_date": date.today().isoformat()},
        ).execute()
    except Exception:
        logger.warning("Failed to update rate-limit counter for %s", user_id)

    # Fire analysis in the background (non-blocking)
    asyncio.create_task(
        run_analysis(
            task_id=task_id,
            ticker=ticker,
            user_id=user_id,
            trade_date=trade_date,
        )
    )

    return {"task_id": task_id, "status": "queued"}


def _assert_task_ownership(task_id: str, user_id: str, supabase: Client) -> None:
    """Raise 404 if task does not exist or does not belong to this user."""
    result = (
        supabase.table("analyses")
        .select("user_id")
        .eq("id", task_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")
    if result.data[0]["user_id"] != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Analysis not found")


@router.get("/{task_id}/status")
async def get_analysis_status(
    task_id: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """
    Poll progress for a submitted analysis.

    Returns per-agent status list for the Analyst Briefing Room UI.
    """
    _assert_task_ownership(task_id, user["id"], supabase)

    task = get_task(task_id)
    if task is None:
        # Task may have been submitted but not yet picked up by the worker
        return {
            "task_id": task_id,
            "status": "queued",
            "agents": [
                {"name": n, "status": "queued", "summary": None} for n in AGENT_NAMES
            ],
            "progress_pct": 0,
        }

    return {
        "task_id": task_id,
        "status": task["status"],
        "agents": task["agents"],
        "progress_pct": task["progress_pct"],
    }


@router.get("/{task_id}/result")
async def get_analysis_result(
    task_id: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """
    Retrieve the full result of a completed analysis.

    Returns 404 if the analysis is not yet complete.
    """
    _assert_task_ownership(task_id, user["id"], supabase)

    task = get_task(task_id)
    if task is None or task["status"] != "complete":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Analysis not complete yet",
        )

    return {
        "task_id": task_id,
        "ticker": task["ticker"],
        "trade_date": task.get("trade_date"),
        "result": task["result"],
    }
