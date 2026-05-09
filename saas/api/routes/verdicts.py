"""AI track record: historical verdicts + settlement outcomes."""
import logging

from fastapi import APIRouter, Depends, Query
from supabase import Client

from saas.api.deps import get_current_user, get_supabase

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("")
async def list_verdicts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    settled_only: bool = Query(default=False),
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """
    Return the authenticated user's verdict track record.

    Include settlement data (30d / 90d price vs SPX) for completed verdicts.
    """
    query = (
        supabase.table("verdicts")
        .select(
            "id, ticker, verdict_date, verdict, "
            "price_at_verdict, price_30d, price_90d, "
            "spx_price_at_verdict, spx_price_30d, spx_price_90d, "
            "settled_30d, settled_90d, created_at, "
            "analyses(conviction, conviction_pct, summary_text)"
        )
        .eq("user_id", user["id"])
        .order("verdict_date", desc=True)
        .range(offset, offset + limit - 1)
    )

    if settled_only:
        query = query.eq("settled_30d", True)

    result = query.execute()
    items = result.data or []

    # Compute hit-rate summary for the caller
    total_settled = sum(1 for v in items if v.get("settled_30d"))
    wins = 0
    for v in items:
        if not v.get("settled_30d") or v.get("price_at_verdict") is None or v.get("price_30d") is None:
            continue
        stock_return = (v["price_30d"] - v["price_at_verdict"]) / v["price_at_verdict"]
        spx_return = 0.0
        if v.get("spx_price_at_verdict") and v.get("spx_price_30d"):
            spx_return = (v["spx_price_30d"] - v["spx_price_at_verdict"]) / v["spx_price_at_verdict"]

        # A BULLISH verdict wins if the stock beat SPX; BEARISH wins if it underperformed
        if v["verdict"] == "BULLISH" and stock_return >= spx_return:
            wins += 1
        elif v["verdict"] == "BEARISH" and stock_return < spx_return:
            wins += 1
        elif v["verdict"] == "NEUTRAL":
            # Neutral is directionally uncountable; skip from win/loss
            total_settled = max(0, total_settled - 1)

    hit_rate = round(wins / total_settled * 100, 1) if total_settled > 0 else None

    return {
        "verdicts": items,
        "summary": {
            "total": len(items),
            "settled_30d": total_settled,
            "wins_30d": wins,
            "hit_rate_pct": hit_rate,
        },
    }


def _is_correct_30d(v: dict) -> bool:
    """
    Correctness rules:
    - BULLISH: stock 30d return > SPX 30d return + 2%
    - BEARISH: stock 30d return < SPX 30d return - 2%
    - NEUTRAL: abs(stock 30d return - SPX 30d return) < 5%
    """
    if not v.get("price_at_verdict") or not v.get("price_30d"):
        return False
    stock_return = (v["price_30d"] - v["price_at_verdict"]) / v["price_at_verdict"]
    spx_return = 0.0
    if v.get("spx_price_at_verdict") and v.get("spx_price_30d"):
        spx_return = (v["spx_price_30d"] - v["spx_price_at_verdict"]) / v["spx_price_at_verdict"]

    verdict = v.get("verdict", "NEUTRAL")
    if verdict == "BULLISH":
        return stock_return > spx_return + 0.02
    elif verdict == "BEARISH":
        return stock_return < spx_return - 0.02
    else:  # NEUTRAL
        return abs(stock_return - spx_return) < 0.05


@router.get("/summary")
async def verdict_summary(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """
    Full accuracy stats for all settled verdicts.

    A bullish verdict is 'correct' if 30d return > SPX 30d return + 2%.
    A bearish verdict is 'correct' if 30d return < SPX 30d return - 2%.
    A neutral verdict is 'correct' if abs(30d return - SPX 30d return) < 5%.
    """
    result = (
        supabase.table("verdicts")
        .select("*")
        .eq("user_id", user["id"])
        .eq("settled_30d", True)
        .execute()
    )

    verdicts = result.data or []
    if not verdicts:
        return {
            "total_settled": 0,
            "accuracy_30d": None,
            "by_type": {},
            "message": "Track record unlocks after 30 days of verdicts.",
        }

    by_type: dict[str, dict] = {
        "BULLISH": {"total": 0, "correct": 0},
        "BEARISH": {"total": 0, "correct": 0},
        "NEUTRAL": {"total": 0, "correct": 0},
    }
    total_correct = 0

    for v in verdicts:
        vtype = v.get("verdict", "NEUTRAL")
        if vtype not in by_type:
            continue
        by_type[vtype]["total"] += 1
        if _is_correct_30d(v):
            by_type[vtype]["correct"] += 1
            total_correct += 1

    accuracy = round(total_correct / len(verdicts) * 100, 1) if verdicts else None

    return {
        "total_settled": len(verdicts),
        "total_correct": total_correct,
        "accuracy_30d": accuracy,
        "by_type": {
            k: {
                "total": bv["total"],
                "correct": bv["correct"],
                "accuracy": round(bv["correct"] / bv["total"] * 100, 1) if bv["total"] else None,
            }
            for k, bv in by_type.items()
        },
    }
