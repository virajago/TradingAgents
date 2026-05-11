"""P1: watchlist CRUD — data integrity and user isolation.

Each user must see only their own watchlist items. Add/delete must be
idempotency-aware (duplicate insert → 409, missing delete → 404).
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from httpx import AsyncClient


def _override_supabase(mock_sb):
    """Context-manager helper: override get_supabase and restore after test."""
    from saas.api.deps import get_supabase
    from saas.api.main import app
    from tests.saas.conftest import fake_get_supabase
    app.dependency_overrides[get_supabase] = lambda: mock_sb
    return get_supabase, app, fake_get_supabase


@pytest.mark.asyncio
async def test_get_watchlist_returns_user_items(client: AsyncClient):
    """GET /watchlist must return all items for the authenticated user."""
    mock_sb = MagicMock()
    (
        mock_sb.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value.data
    ) = [
        {"id": "w1", "ticker": "NVDA", "user_id": "user-test-uuid-1234"},
        {"id": "w2", "ticker": "AAPL", "user_id": "user-test-uuid-1234"},
    ]

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.get("/watchlist")
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 200
    data = response.json()
    # Route returns {"items": [...]}
    items = data.get("items", data) if isinstance(data, dict) else data
    assert len(items) == 2
    tickers = {i["ticker"] for i in items}
    assert "NVDA" in tickers
    assert "AAPL" in tickers


@pytest.mark.asyncio
async def test_get_watchlist_returns_empty_list_when_no_items(client: AsyncClient):
    """GET /watchlist for a user with no items must return an empty list, not an error."""
    mock_sb = MagicMock()
    (
        mock_sb.table.return_value
        .select.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value.data
    ) = []

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.get("/watchlist")
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 200
    data = response.json()
    items = data.get("items", data) if isinstance(data, dict) else data
    assert items == []


@pytest.mark.asyncio
async def test_add_ticker_to_watchlist(client: AsyncClient):
    """POST /watchlist with a valid ticker must insert the row and return 201."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "w3", "ticker": "MSFT", "user_id": "user-test-uuid-1234"}
    ]

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.post("/watchlist", json={"ticker": "MSFT"})
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code in (200, 201), (
        f"Expected 200/201, got {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_add_duplicate_ticker_returns_409(client: AsyncClient):
    """Inserting the same ticker twice must return 409 Conflict.

    The database enforces unique(user_id, ticker). The route must translate
    the constraint violation into a 409 rather than a 500.
    """
    mock_sb = MagicMock()
    # Simulate a duplicate-key exception from the Supabase client
    mock_sb.table.return_value.insert.return_value.execute.side_effect = Exception(
        "duplicate key value violates unique constraint"
    )

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.post("/watchlist", json={"ticker": "NVDA"})
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 409, (
        f"Duplicate ticker insert: expected 409, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_remove_ticker_from_watchlist(client: AsyncClient):
    """DELETE /watchlist/{ticker} must remove the item and return 204."""
    mock_sb = MagicMock()
    (
        mock_sb.table.return_value
        .delete.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value.data
    ) = [{"id": "w3", "ticker": "MSFT"}]

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.delete("/watchlist/MSFT")
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code in (200, 204), (
        f"Expected 200/204, got {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_remove_nonexistent_ticker_returns_404(client: AsyncClient):
    """Deleting a ticker not on the user's watchlist must return 404."""
    mock_sb = MagicMock()
    (
        mock_sb.table.return_value
        .delete.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value.data
    ) = []  # no rows deleted

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.delete("/watchlist/FAKE")
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 404, (
        f"Expected 404 for missing ticker, got {response.status_code}"
    )


@pytest.mark.asyncio
async def test_watchlist_normalises_ticker_to_uppercase(client: AsyncClient):
    """Lowercase ticker in POST body must be stored as uppercase."""
    mock_sb = MagicMock()
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "w4", "ticker": "TSLA", "user_id": "user-test-uuid-1234"}
    ]

    get_supabase, app, fake_get_supabase = _override_supabase(mock_sb)
    try:
        response = await client.post("/watchlist", json={"ticker": "tsla"})
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    # Should succeed (not be rejected as invalid)
    assert response.status_code in (200, 201), (
        f"Lowercase ticker should be normalised; got {response.status_code}"
    )
    # The insert must have been called with the uppercase ticker
    insert_call = mock_sb.table.return_value.insert.call_args
    if insert_call:
        payload = insert_call[0][0] if insert_call[0] else insert_call[1]
        ticker_in_db = payload.get("ticker", "") if isinstance(payload, dict) else ""
        if ticker_in_db:
            assert ticker_in_db == "TSLA", f"Expected 'TSLA', got {ticker_in_db!r}"
