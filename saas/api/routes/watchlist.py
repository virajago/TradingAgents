"""Watchlist CRUD — tickers queued for weekly Sunday analysis."""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from saas.api.deps import get_current_user, get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()

_TICKER_RE = re.compile(r"^[A-Z0-9]{1,8}$")


def _validate_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticker: must be 1-8 uppercase alphanumeric characters",
        )
    return ticker


class WatchlistAddRequest(BaseModel):
    ticker: str


@router.get("")
async def list_watchlist(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Return all tickers on the authenticated user's watchlist."""
    result = (
        supabase.table("watchlist_items")
        .select("id, ticker, added_at")
        .eq("user_id", user["id"])
        .order("added_at", desc=False)
        .execute()
    )
    return {"items": result.data or []}


@router.post("", status_code=status.HTTP_201_CREATED)
async def add_to_watchlist(
    body: WatchlistAddRequest,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Add a ticker to the user's watchlist."""
    ticker = _validate_ticker(body.ticker)

    try:
        result = (
            supabase.table("watchlist_items")
            .insert({"user_id": user["id"], "ticker": ticker})
            .execute()
        )
    except Exception as exc:
        # Duplicate key from unique(user_id, ticker) constraint
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{ticker} is already on your watchlist",
            )
        logger.exception("Failed to add %s to watchlist for %s", ticker, user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add ticker",
        )

    return result.data[0]


@router.delete("/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_watchlist(
    ticker: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> None:
    """Remove a ticker from the user's watchlist."""
    ticker = _validate_ticker(ticker)

    result = (
        supabase.table("watchlist_items")
        .delete()
        .eq("user_id", user["id"])
        .eq("ticker", ticker)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ticker} not found on watchlist",
        )
