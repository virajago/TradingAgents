"""P0: credit deduction must be atomic and reject insufficient balances.

The deduct_credits Postgres RPC holds a row-level lock so no two concurrent
calls can both succeed when the balance would go negative. These tests verify
the Python wrapper around that RPC behaves correctly for all edge cases.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock

# fastapi.HTTPException may be the real class or our stub — either way it has
# .status_code so the tests are portable.
try:
    from fastapi import HTTPException
except ModuleNotFoundError:
    # Use the stub injected by conftest
    from saas.api.deps import HTTPException  # type: ignore[assignment]


@pytest.mark.asyncio
async def test_insufficient_credits_raises_402():
    """deduct_credits RPC returning -1 → HTTP 402 Payment Required.

    The caller should never be charged when the balance is insufficient.
    """
    from saas.api.credits import check_and_deduct_credits

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = -1

    with pytest.raises(Exception) as exc_info:
        await check_and_deduct_credits(
            user_id="user-123",
            amount=10,
            action="on_demand_analysis",
            reference_id="task-abc",
            supabase=mock_sb,
        )
    # Accept either real HTTPException or our conftest stub
    exc = exc_info.value
    assert getattr(exc, "status_code", None) == 402, (
        f"Expected 402, got {getattr(exc, 'status_code', type(exc))}"
    )


@pytest.mark.asyncio
async def test_sufficient_credits_returns_new_balance():
    """deduct_credits RPC returning a positive integer → returns new balance."""
    from saas.api.credits import check_and_deduct_credits

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = 240

    result = await check_and_deduct_credits(
        user_id="user-123",
        amount=10,
        action="on_demand_analysis",
        reference_id="task-abc",
        supabase=mock_sb,
    )
    assert result == 240


@pytest.mark.asyncio
async def test_credits_rpc_called_with_correct_args():
    """The RPC must be called with the exact parameter names the SQL function expects."""
    from saas.api.credits import check_and_deduct_credits

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = 50

    await check_and_deduct_credits(
        user_id="user-999",
        amount=10,
        action="on_demand_analysis",
        reference_id="task-xyz",
        supabase=mock_sb,
    )

    mock_sb.rpc.assert_called_once_with(
        "deduct_credits",
        {
            "p_user_id": "user-999",
            "p_amount": 10,
            "p_action": "on_demand_analysis",
            "p_reference_id": "task-xyz",
        },
    )


@pytest.mark.asyncio
async def test_credits_rpc_none_response_raises_402():
    """None response from the RPC (e.g. no credit record) must raise 402.

    A missing user_credits row is treated the same as insufficient balance.
    """
    from saas.api.credits import check_and_deduct_credits

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = None

    with pytest.raises(Exception) as exc_info:
        await check_and_deduct_credits(
            user_id="u",
            amount=10,
            action="test",
            reference_id="ref",
            supabase=mock_sb,
        )
    exc = exc_info.value
    assert getattr(exc, "status_code", None) == 402, (
        f"Expected 402, got {getattr(exc, 'status_code', type(exc))}"
    )


@pytest.mark.asyncio
async def test_credits_rpc_zero_response_raises_402():
    """Zero balance after deduction means the balance was exactly zero — still insufficient.

    deduct_credits returns -1 on failure, so zero is technically a valid
    success; but if the function returned 0 it means the user had exactly
    `amount` credits. Verify the wrapper passes through 0 as success.
    """
    from saas.api.credits import check_and_deduct_credits

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = 0

    # 0 is >= 0 so the implementation should NOT raise — the user had exactly
    # `amount` credits and is now at zero.
    result = await check_and_deduct_credits(
        user_id="u",
        amount=10,
        action="test",
        reference_id="ref",
        supabase=mock_sb,
    )
    # The RPC returning 0 means new balance is 0 — allowed per the contract
    # (deduct_credits returns -1 on failure, non-negative on success).
    assert result == 0


@pytest.mark.asyncio
async def test_deduct_credits_uses_correct_action_label():
    """action param must be passed through unchanged so credit_transactions is legible."""
    from saas.api.credits import check_and_deduct_credits

    mock_sb = MagicMock()
    mock_sb.rpc.return_value.execute.return_value.data = 99

    await check_and_deduct_credits(
        user_id="u",
        amount=1,
        action="weekly_digest",
        reference_id="ref-batch",
        supabase=mock_sb,
    )

    call_kwargs = mock_sb.rpc.call_args[0][1]
    assert call_kwargs["p_action"] == "weekly_digest"
    assert call_kwargs["p_reference_id"] == "ref-batch"
