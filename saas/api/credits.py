"""Credit deduction helper — atomic check-and-deduct via Postgres RPC."""
from fastapi import HTTPException, status
from supabase import Client


async def check_and_deduct_credits(
    user_id: str,
    amount: int,
    action: str,
    reference_id: str,
    supabase: Client,
) -> int:
    """
    Atomically verify the user has at least `amount` credits and deduct them.

    Returns the new balance on success. Raises HTTP 402 if the user has no
    credit record or an insufficient balance. The underlying Postgres function
    (deduct_credits) holds a row-level lock so concurrent calls cannot both
    succeed when the balance would go negative.
    """
    result = supabase.rpc(
        "deduct_credits",
        {
            "p_user_id": user_id,
            "p_amount": amount,
            "p_action": action,
            "p_reference_id": reference_id,
        },
    ).execute()

    # deduct_credits returns -1 on no-record or insufficient balance
    if result.data is None or result.data < 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient credits. {amount} required for action: {action}",
        )
    return result.data
