"""P0: internal routes must be protected by INTERNAL_API_SECRET.

The /internal/* routes are called by Cloud Scheduler, not by users. A missing
secret header (or wrong secret) must always result in 401/403, never 200.
The 'client' fixture overrides verify_internal_secret so the positive-case
test can verify the route itself works once auth passes.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch
from httpx import AsyncClient


INTERNAL_ROUTES = [
    "/internal/batch/run",
    "/internal/alerts/check",
    "/internal/verdicts/settle",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("path", INTERNAL_ROUTES)
async def test_internal_route_rejects_missing_secret(
    unauthed_client: AsyncClient, path: str
):
    """No x-internal-secret header must return 401/403/422 — never 200.

    Without the header FastAPI either raises 422 (missing required header) or
    the dependency raises 403. Both are acceptable rejections.
    """
    response = await unauthed_client.post(path)
    assert response.status_code in (401, 403, 422), (
        f"POST {path} returned {response.status_code} without secret header"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", INTERNAL_ROUTES)
async def test_internal_route_rejects_wrong_secret(
    unauthed_client: AsyncClient, path: str
):
    """A wrong x-internal-secret value must return 403 Forbidden."""
    response = await unauthed_client.post(
        path, headers={"x-internal-secret": "definitely-wrong-secret"}
    )
    assert response.status_code in (401, 403), (
        f"POST {path} accepted wrong secret: {response.status_code}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("path", INTERNAL_ROUTES)
async def test_internal_route_accepts_correct_secret(
    client: AsyncClient, path: str
):
    """client fixture overrides verify_internal_secret → must NOT be 401/403.

    Background tasks are patched so no real worker code runs.
    """
    with patch("fastapi.BackgroundTasks.add_task", return_value=None):
        response = await client.post(
            path, headers={"x-internal-secret": "test-secret"}
        )
    assert response.status_code not in (401, 403), (
        f"POST {path} rejected even with auth overridden: {response.status_code}"
    )


@pytest.mark.asyncio
async def test_health_endpoint_is_public(unauthed_client: AsyncClient):
    """GET /health must be publicly accessible — no auth required.

    Load balancers and uptime monitors rely on this endpoint.
    """
    response = await unauthed_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_batch_run_starts_background_task(client: AsyncClient):
    """POST /internal/batch/run must enqueue the weekly batch and return 'batch_started'."""
    with patch("fastapi.BackgroundTasks.add_task") as mock_add:
        response = await client.post("/internal/batch/run")
    assert response.status_code == 200
    assert response.json().get("status") == "batch_started"


@pytest.mark.asyncio
async def test_alerts_check_starts_background_task(client: AsyncClient):
    """POST /internal/alerts/check must enqueue alert monitoring."""
    with patch("fastapi.BackgroundTasks.add_task"):
        response = await client.post("/internal/alerts/check")
    assert response.status_code == 200
    assert response.json().get("status") == "alert_check_started"


@pytest.mark.asyncio
async def test_verdicts_settle_starts_background_task(client: AsyncClient):
    """POST /internal/verdicts/settle must enqueue verdict settlement."""
    with patch("fastapi.BackgroundTasks.add_task"):
        response = await client.post("/internal/verdicts/settle")
    assert response.status_code == 200
    assert response.json().get("status") == "settlement_started"
