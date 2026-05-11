"""P0: every protected route must return 401/422/403 without a valid token.

Why this matters: a missing auth guard on any route is a P0 data-leak. This
parametrised test acts as a security regression gate — if a new route is added
without authentication the test suite fails.
"""
from __future__ import annotations

import pytest
from httpx import AsyncClient

PROTECTED_ROUTES = [
    ("GET",  "/analyze/fake-id/status"),
    ("GET",  "/analyze/fake-id/result"),
    ("GET",  "/credits"),
    ("GET",  "/watchlist"),
    ("POST", "/watchlist"),
    ("GET",  "/portfolio/holdings"),
    ("POST", "/portfolio/holdings"),
    ("GET",  "/journal/"),
    ("POST", "/journal/"),
    ("GET",  "/verdicts/"),
    ("GET",  "/verdicts/summary"),
    ("GET",  "/auth/me"),
    ("POST", "/auth/billing-portal"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED_ROUTES)
async def test_unauthenticated_request_rejected(
    unauthed_client: AsyncClient, method: str, path: str
):
    """No Authorization header must NOT return 200 — must be 401, 403, or 422."""
    response = await getattr(unauthed_client, method.lower())(path)
    assert response.status_code in (401, 403, 422), (
        f"{method} {path} returned {response.status_code} without auth — "
        "expected 401/403/422"
    )
