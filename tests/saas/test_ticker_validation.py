"""P0: ticker input must be validated and sanitized at every entry point.

Malformed tickers (path traversal, special chars, empty strings, overlong
symbols) must be rejected before they can influence file-system paths,
database queries, or downstream API calls.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock


@pytest.mark.asyncio
async def test_analyze_rejects_empty_ticker(client: AsyncClient):
    """Empty string is not a valid ticker — must be rejected with 422."""
    response = await client.post("/analyze", json={"ticker": ""})
    assert response.status_code in (400, 422), (
        f"Empty ticker accepted with status {response.status_code}"
    )


@pytest.mark.asyncio
async def test_analyze_rejects_path_traversal(client: AsyncClient):
    """../etc/passwd style path traversal must be rejected (400 or 422)."""
    response = await client.post("/analyze", json={"ticker": "../etc/passwd"})
    assert response.status_code in (400, 422), (
        f"Path traversal ticker accepted with status {response.status_code}"
    )


@pytest.mark.asyncio
async def test_analyze_rejects_too_long_ticker(client: AsyncClient):
    """Tickers longer than 8 characters are not valid exchange symbols."""
    response = await client.post("/analyze", json={"ticker": "TOOLONGTICKERXYZ"})
    assert response.status_code in (400, 422), (
        f"Overlong ticker accepted with status {response.status_code}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_ticker", [
    "NV;DA",
    "NV DA",
    "NV\x00DA",
    "NV<DA>",
    "../../",
    "NV%20DA",
])
async def test_analyze_rejects_special_chars(client: AsyncClient, bad_ticker: str):
    """Tickers with shell/SQL/path special characters must be rejected."""
    response = await client.post("/analyze", json={"ticker": bad_ticker})
    assert response.status_code in (400, 422), (
        f"Accepted bad ticker {bad_ticker!r} with status {response.status_code}"
    )


@pytest.mark.asyncio
async def test_analyze_accepts_valid_ticker(client: AsyncClient):
    """A well-formed ticker (1-8 uppercase alphanumeric) must pass validation.

    The test mocks credit-deduction and task creation so no real analysis runs;
    the important assertion is that validation does NOT reject a valid symbol.
    """
    mock_sb = MagicMock()
    # Simulate active subscription profile lookup
    profile_chain = mock_sb.table.return_value.select.return_value.eq.return_value
    profile_chain.execute.return_value.data = [{"subscription_status": "active"}]
    # Simulate rate-limit table returning no existing count
    mock_sb.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
    mock_sb.rpc.return_value.execute.return_value.data = 240  # credits after deduction
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{}]

    from saas.api.deps import get_supabase
    from saas.api.main import app

    app.dependency_overrides[get_supabase] = lambda: mock_sb

    try:
        with patch(
            "saas.api.routes.analyze.check_and_deduct_credits",
            new_callable=AsyncMock,
            return_value=240,
        ), patch("saas.api.routes.analyze.asyncio.create_task"):
            response = await client.post("/analyze", json={"ticker": "NVDA"})
    finally:
        # Restore the original override from conftest
        from tests.saas.conftest import fake_get_supabase
        app.dependency_overrides[get_supabase] = fake_get_supabase

    # Must not be a FastAPI validation error (422). The route may still return
    # 402 (no credits), 403 (no subscription), or 202 (accepted).
    assert response.status_code != 422, (
        f"Valid ticker 'NVDA' was rejected by validation: {response.json()}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_ticker", [
    "",
    "../bad",
    "TOOLONGNAME",
    "NV;DA",
    "NV DA",
])
async def test_watchlist_rejects_invalid_ticker(client: AsyncClient, bad_ticker: str):
    """Watchlist add endpoint must enforce the same ticker validation as analyze."""
    response = await client.post("/watchlist", json={"ticker": bad_ticker})
    assert response.status_code in (400, 422), (
        f"Watchlist accepted bad ticker {bad_ticker!r} with status "
        f"{response.status_code}"
    )


@pytest.mark.asyncio
async def test_watchlist_accepts_valid_ticker(client: AsyncClient):
    """Valid ticker must be inserted into the watchlist (status 201)."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "w1", "ticker": "AAPL", "user_id": "user-test-uuid-1234"}
    ]

    from saas.api.deps import get_supabase
    from saas.api.main import app
    from tests.saas.conftest import fake_get_supabase

    app.dependency_overrides[get_supabase] = lambda: mock_sb
    try:
        response = await client.post("/watchlist", json={"ticker": "AAPL"})
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code in (200, 201), (
        f"Valid ticker 'AAPL' rejected: {response.status_code} {response.text}"
    )
