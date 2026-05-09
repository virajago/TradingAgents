"""Portfolio holdings CRUD. All data is user-scoped via RLS."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from supabase import Client

from saas.api.deps import get_current_user, get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


class HoldingCreate(BaseModel):
    ticker: str
    shares: int
    avg_cost_usd: float

    @field_validator("ticker")
    @classmethod
    def ticker_uppercase(cls, v: str) -> str:
        v = v.upper().strip()
        if not v.isalpha() or len(v) > 8:
            raise ValueError("Ticker must be 1-8 letters")
        return v

    @field_validator("shares")
    @classmethod
    def shares_positive(cls, v: int) -> int:
        if v < 1:
            raise ValueError("Shares must be a positive integer")
        return v

    @field_validator("avg_cost_usd")
    @classmethod
    def cost_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Average cost must be positive")
        return round(v, 2)


class HoldingUpdate(BaseModel):
    shares: int | None = None
    avg_cost_usd: float | None = None


@router.get("/holdings")
async def list_holdings(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    result = supabase.table("portfolio_holdings").select("*").eq(
        "user_id", user["id"]
    ).order("added_at").execute()
    return result.data or []


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
async def add_holding(
    body: HoldingCreate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    result = supabase.table("portfolio_holdings").upsert({
        "user_id": user["id"],
        "ticker": body.ticker,
        "shares": body.shares,
        "avg_cost_usd": body.avg_cost_usd,
    }, on_conflict="user_id,ticker").execute()
    return result.data[0] if result.data else {}


@router.put("/holdings/{ticker}")
async def update_holding(
    ticker: str,
    body: HoldingUpdate,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    ticker = ticker.upper()
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = supabase.table("portfolio_holdings").update(updates).eq(
        "user_id", user["id"]
    ).eq("ticker", ticker).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail=f"{ticker} not in portfolio")
    return result.data[0]


@router.delete("/holdings/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    ticker: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    ticker = ticker.upper()
    supabase.table("portfolio_holdings").delete().eq(
        "user_id", user["id"]
    ).eq("ticker", ticker).execute()


@router.get("/summary")
async def portfolio_summary(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Return holdings with cost-basis summary. Current prices not fetched (Phase 1B enhancement)."""
    result = supabase.table("portfolio_holdings").select("*").eq(
        "user_id", user["id"]
    ).execute()
    holdings = result.data or []
    total_invested = sum(h["shares"] * float(h["avg_cost_usd"]) for h in holdings)
    return {
        "holdings": holdings,
        "total_invested_usd": round(total_invested, 2),
        "position_count": len(holdings),
    }
