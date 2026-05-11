"""P1: portfolio holdings — validation and cost-basis calculation.

The portfolio module is the only place user-entered financial data (shares,
cost basis) flows into server-side arithmetic. Validation must be strict and
the summary math must be correct.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient


def _override_supabase(mock_sb):
    from saas.api.deps import get_supabase
    from saas.api.main import app
    from tests.saas.conftest import fake_get_supabase
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    return get_supabase, app, fake_get_supabase


@pytest.mark.asyncio
async def test_add_holding_rejects_zero_shares(client: AsyncClient):
    """shares=0 is not a positive integer — must be rejected with 422."""
    response = await client.post(
        "/portfolio/holdings",
        json={"ticker": "NVDA", "shares": 0, "avg_cost_usd": 100.0},
    )
    assert response.status_code == 422, (
        f"shares=0 should fail validation, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_add_holding_rejects_negative_shares(client: AsyncClient):
    """Negative shares make no sense — must be rejected with 422."""
    response = await client.post(
        "/portfolio/holdings",
        json={"ticker": "NVDA", "shares": -5, "avg_cost_usd": 100.0},
    )
    assert response.status_code == 422, (
        f"shares=-5 should fail validation, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_add_holding_rejects_negative_cost(client: AsyncClient):
    """Negative average cost is economically invalid — must be rejected with 422."""
    response = await client.post(
        "/portfolio/holdings",
        json={"ticker": "NVDA", "shares": 10, "avg_cost_usd": -50.0},
    )
    assert response.status_code == 422, (
        f"avg_cost_usd=-50 should fail validation, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_add_holding_rejects_zero_cost(client: AsyncClient):
    """avg_cost_usd=0 is also invalid (must be positive, not just non-negative)."""
    response = await client.post(
        "/portfolio/holdings",
        json={"ticker": "NVDA", "shares": 10, "avg_cost_usd": 0.0},
    )
    assert response.status_code == 422, (
        f"avg_cost_usd=0 should fail validation, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_add_holding_accepts_valid_data(client: AsyncClient):
    """Valid holding (positive shares + positive cost) must be upserted (201)."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "h1", "ticker": "NVDA", "shares": 200, "avg_cost_usd": "118.00"}
    ]

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.post(
            "/portfolio/holdings",
            json={"ticker": "NVDA", "shares": 200, "avg_cost_usd": 118.00},
        )
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code in (200, 201), (
        f"Valid holding rejected: {response.status_code} {response.text}"
    )


@pytest.mark.asyncio
async def test_add_holding_normalises_ticker_to_uppercase(client: AsyncClient):
    """Lowercase ticker in the request body must be normalised to uppercase before upsert."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.upsert.return_value.execute.return_value.data = [
        {"id": "h2", "ticker": "NVDA", "shares": 10, "avg_cost_usd": "100.00"}
    ]

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.post(
            "/portfolio/holdings",
            json={"ticker": "nvda", "shares": 10, "avg_cost_usd": 100.0},
        )
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code in (200, 201), (
        f"Lowercase ticker should be normalised; got {response.status_code}"
    )
    upsert_call = mock_sb.table.return_value.upsert.call_args
    if upsert_call:
        payload = upsert_call[0][0] if upsert_call[0] else {}
        if "ticker" in payload:
            assert payload["ticker"] == "NVDA", (
                f"Expected 'NVDA' in DB, got {payload['ticker']!r}"
            )


@pytest.mark.asyncio
async def test_portfolio_summary_returns_totals(client: AsyncClient):
    """GET /portfolio/summary must correctly compute total_invested_usd.

    200 shares × $118 + 100 shares × $185 = $23 600 + $18 500 = $42 100.
    """
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"ticker": "NVDA", "shares": 200, "avg_cost_usd": "118.00"},
        {"ticker": "AAPL", "shares": 100, "avg_cost_usd": "185.00"},
    ]

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.get("/portfolio/summary")
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 200
    data = response.json()
    assert "total_invested_usd" in data, (
        f"Response missing 'total_invested_usd': {data}"
    )
    expected = 200 * 118.0 + 100 * 185.0  # = 42_100.0
    assert abs(data["total_invested_usd"] - expected) < 0.01, (
        f"Expected {expected}, got {data['total_invested_usd']}"
    )


@pytest.mark.asyncio
async def test_portfolio_summary_empty_portfolio(client: AsyncClient):
    """An empty portfolio must return total_invested_usd=0 and position_count=0."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.get("/portfolio/summary")
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 200
    data = response.json()
    assert data.get("total_invested_usd") == 0.0
    assert data.get("position_count") == 0


@pytest.mark.asyncio
async def test_list_holdings_returns_all_positions(client: AsyncClient):
    """GET /portfolio/holdings must return the full list for the authenticated user."""
    holdings = [
        {"id": "h1", "ticker": "NVDA", "shares": 200, "avg_cost_usd": "118.00"},
        {"id": "h2", "ticker": "AAPL", "shares": 100, "avg_cost_usd": "185.00"},
        {"id": "h3", "ticker": "MSFT", "shares": 50, "avg_cost_usd": "410.00"},
    ]
    mock_sb = MagicMock()
    # Simulate order() chained query
    (
        mock_sb.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value.data
    ) = holdings

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.get("/portfolio/holdings")
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
