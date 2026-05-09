"""Portfolio holdings CRUD."""
import logging
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
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


class HoldingUpsertRequest(BaseModel):
    ticker: str
    shares: int
    avg_cost_usd: float

    @field_validator("shares")
    @classmethod
    def shares_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("shares must be positive")
        return v

    @field_validator("avg_cost_usd")
    @classmethod
    def cost_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("avg_cost_usd must be positive")
        return v


@router.get("/holdings")
async def list_holdings(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Return all portfolio holdings for the authenticated user."""
    result = (
        supabase.table("portfolio_holdings")
        .select("id, ticker, shares, avg_cost_usd, added_at, updated_at")
        .eq("user_id", user["id"])
        .order("ticker", desc=False)
        .execute()
    )
    return {"holdings": result.data or []}


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
async def add_holding(
    body: HoldingUpsertRequest,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Add a new holding. Returns 409 if the ticker already exists (use PUT to update)."""
    ticker = _validate_ticker(body.ticker)

    try:
        result = (
            supabase.table("portfolio_holdings")
            .insert(
                {
                    "user_id": user["id"],
                    "ticker": ticker,
                    "shares": body.shares,
                    "avg_cost_usd": body.avg_cost_usd,
                }
            )
            .execute()
        )
    except Exception as exc:
        if "duplicate" in str(exc).lower() or "unique" in str(exc).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"{ticker} already in portfolio — use PUT to update",
            )
        logger.exception("Failed to add holding %s for %s", ticker, user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to add holding",
        )

    return result.data[0]


@router.put("/holdings/{ticker}")
async def update_holding(
    ticker: str,
    body: HoldingUpsertRequest,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Update shares and average cost for an existing holding."""
    ticker = _validate_ticker(ticker)

    result = (
        supabase.table("portfolio_holdings")
        .update(
            {
                "shares": body.shares,
                "avg_cost_usd": body.avg_cost_usd,
                "updated_at": "now()",
            }
        )
        .eq("user_id", user["id"])
        .eq("ticker", ticker)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ticker} not found in portfolio",
        )
    return result.data[0]


@router.delete("/holdings/{ticker}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    ticker: str,
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> None:
    """Remove a holding from the portfolio."""
    ticker = _validate_ticker(ticker)

    result = (
        supabase.table("portfolio_holdings")
        .delete()
        .eq("user_id", user["id"])
        .eq("ticker", ticker)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{ticker} not found in portfolio",
        )
