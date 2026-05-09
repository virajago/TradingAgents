"""Decision journal CRUD."""
import logging
import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from supabase import Client

from saas.api.deps import get_current_user, get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()

_VALID_ACTIONS = {"buy", "sell", "hold", "wait", "skip"}
_TICKER_RE = re.compile(r"^[A-Z0-9]{1,8}$")


def _validate_ticker(raw: str) -> str:
    ticker = raw.strip().upper()
    if not _TICKER_RE.match(ticker):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid ticker: must be 1-8 uppercase alphanumeric characters",
        )
    return ticker


class JournalEntryRequest(BaseModel):
    ticker: str
    action: str
    thesis: Optional[str] = None
    analysis_id: Optional[str] = None
    entry_date: Optional[str] = None  # ISO date string; defaults to today
    price_at_entry: Optional[float] = None


@router.get("")
async def list_journal(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Return the authenticated user's journal entries newest first, with linked analysis if available."""
    result = (
        supabase.table("journal_entries")
        .select(
            "id, ticker, action, thesis, entry_date, analysis_id, "
            "price_at_entry, price_30d, price_90d, created_at, "
            "analyses(ticker, verdict, conviction, conviction_pct, summary_text)"
        )
        .eq("user_id", user["id"])
        .order("entry_date", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    return {"entries": result.data or []}


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    body: JournalEntryRequest,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Create a new decision journal entry."""
    ticker = _validate_ticker(body.ticker)

    action = body.action.lower()
    if action not in _VALID_ACTIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"action must be one of: {', '.join(sorted(_VALID_ACTIONS))}",
        )

    entry_date = body.entry_date or date.today().isoformat()

    # Verify analysis belongs to this user if provided
    if body.analysis_id is not None:
        check = (
            supabase.table("analyses")
            .select("id")
            .eq("id", body.analysis_id)
            .eq("user_id", user["id"])
            .execute()
        )
        if not check.data:
            raise HTTPException(status_code=404, detail="Analysis not found")

    row: dict = {
        "user_id": user["id"],
        "ticker": ticker,
        "action": action,
        "entry_date": entry_date,
    }
    if body.thesis is not None:
        row["thesis"] = body.thesis
    if body.analysis_id is not None:
        row["analysis_id"] = body.analysis_id
    if body.price_at_entry is not None:
        row["price_at_entry"] = body.price_at_entry

    try:
        result = supabase.table("journal_entries").insert(row).execute()
    except Exception:
        logger.exception("Failed to create journal entry for %s", user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create journal entry",
        )

    return result.data[0]


@router.get("/{entry_id}")
async def get_entry(
    entry_id: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Return a single journal entry with linked analysis verdict if available."""
    result = (
        supabase.table("journal_entries")
        .select("*, analyses(verdict, conviction, conviction_pct, summary_text)")
        .eq("id", entry_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Entry not found")
    return result.data[0]


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> None:
    """Delete a journal entry owned by the authenticated user."""
    supabase.table("journal_entries").delete().eq(
        "id", entry_id
    ).eq("user_id", user["id"]).execute()
