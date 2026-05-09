"""Credits route — balance and transaction history."""
from fastapi import APIRouter, Depends
from supabase import Client

from saas.api.deps import get_current_user, get_supabase

router = APIRouter()


@router.get("")
async def get_credits(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Return current credit balance and the 20 most recent transactions."""
    user_id = user["id"]

    balance_row = (
        supabase.table("user_credits")
        .select("*")
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    transactions = (
        supabase.table("credit_transactions")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    data = balance_row.data or {}
    return {
        "balance": data.get("balance", 0),
        "lifetime_earned": data.get("lifetime_earned", 0),
        "transactions": transactions.data or [],
    }
