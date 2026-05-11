"""P0: Stripe webhook must verify signature and handle events idempotently.

Two critical properties:
1. Signature verification — a spoofed webhook must be rejected (400).
2. Idempotency — replaying the same event_id must not double-grant credits.
"""
from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient


VALID_SUBSCRIPTION_CREATED = {
    "id": "evt_test_unique_001",
    "type": "customer.subscription.created",
    "data": {
        "object": {
            "id": "sub_test_001",
            "customer": "cus_test_001",
            "status": "trialing",
            "trial_end": 1_800_000_000,
            "items": {"data": [{"price": {"id": "price_starter"}}]},
        }
    },
}

VALID_SUBSCRIPTION_DELETED = {
    "id": "evt_test_unique_002",
    "type": "customer.subscription.deleted",
    "data": {
        "object": {
            "id": "sub_test_001",
            "customer": "cus_test_001",
        }
    },
}


@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(client: AsyncClient):
    """Stripe signature verification failure must return 400.

    Accepting an unsigned payload would allow any attacker to trigger credit
    grants or subscription state changes.
    """
    try:
        import stripe
        # SignatureVerificationError requires (message, sig_header)
        invalid_sig_exc = stripe.error.SignatureVerificationError("Invalid signature", "test-header")
    except Exception:
        invalid_sig_exc = Exception("Invalid signature")

    with patch("stripe.Webhook.construct_event", side_effect=invalid_sig_exc):
        response = await client.post(
            "/webhooks/stripe",
            content=json.dumps(VALID_SUBSCRIPTION_CREATED),
            headers={
                "stripe-signature": "bad_signature",
                "content-type": "application/json",
            },
        )
    assert response.status_code == 400, (
        f"Bad signature accepted with {response.status_code}: {response.text}"
    )


@pytest.mark.asyncio
async def test_webhook_idempotency_skips_duplicate(client: AsyncClient):
    """Second delivery of the same event_id must return 'already_processed'.

    Stripe can deliver the same event multiple times. Processing it twice
    would double-grant credits or double-update subscription state.
    """
    mock_sb = MagicMock()
    # stripe_events table already has this event
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"event_id": "evt_test_unique_001"}
    ]

    from saas.api.deps import get_supabase
    from saas.api.main import app
    from tests.saas.conftest import fake_get_supabase

    app.dependency_overrides[get_supabase] = lambda: mock_sb
    try:
        with patch(
            "stripe.Webhook.construct_event",
            return_value=VALID_SUBSCRIPTION_CREATED,
        ):
            response = await client.post(
                "/webhooks/stripe",
                content=json.dumps(VALID_SUBSCRIPTION_CREATED),
                headers={
                    "stripe-signature": "valid",
                    "content-type": "application/json",
                },
            )
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 200
    assert response.json().get("status") == "already_processed", (
        f"Expected 'already_processed', got: {response.json()}"
    )


@pytest.mark.asyncio
async def test_webhook_processes_new_event(client: AsyncClient):
    """A new event_id (not in stripe_events) must be processed and return 'processed'."""
    mock_sb = MagicMock()
    # stripe_events table does NOT have this event
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # Profile lookup by stripe_customer_id
    mock_sb.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    # resolve_user_id — profiles lookup
    profile_result = MagicMock()
    profile_result.data = [{"id": "user-123"}]
    mock_sb.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [{}]
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{}]
    mock_sb.rpc.return_value.execute.return_value.data = 100

    # Make profiles table .select().eq().execute() return the user id
    def table_side_effect(name):
        tbl = MagicMock()
        tbl.select.return_value.eq.return_value.execute.return_value.data = []
        tbl.insert.return_value.execute.return_value.data = [{}]
        tbl.update.return_value.eq.return_value.execute.return_value.data = [{}]
        if name == "stripe_events":
            tbl.select.return_value.eq.return_value.execute.return_value.data = []
        if name == "profiles":
            tbl.select.return_value.eq.return_value.execute.return_value.data = [{"id": "user-123"}]
        return tbl

    mock_sb.table.side_effect = table_side_effect

    from saas.api.deps import get_supabase
    from saas.api.main import app
    from tests.saas.conftest import fake_get_supabase

    app.dependency_overrides[get_supabase] = lambda: mock_sb
    try:
        with patch(
            "stripe.Webhook.construct_event",
            return_value=VALID_SUBSCRIPTION_CREATED,
        ), patch("saas.api.routes.webhooks.asyncio.create_task"):
            response = await client.post(
                "/webhooks/stripe",
                content=json.dumps(VALID_SUBSCRIPTION_CREATED),
                headers={
                    "stripe-signature": "valid",
                    "content-type": "application/json",
                },
            )
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.status_code == 200
    assert response.json().get("status") == "processed", (
        f"Expected 'processed', got: {response.json()}"
    )


@pytest.mark.asyncio
async def test_webhook_idempotency_does_not_insert_twice(client: AsyncClient):
    """Verify that the stripe_events table insert is not called for a duplicate event.

    This is the internal guarantee: if already_processed is returned, no DB
    write should happen.
    """
    mock_sb = MagicMock()
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"event_id": "evt_test_unique_001"}
    ]
    insert_mock = MagicMock()
    insert_mock.execute.return_value.data = [{}]
    mock_sb.table.return_value.insert.return_value = insert_mock

    from saas.api.deps import get_supabase
    from saas.api.main import app
    from tests.saas.conftest import fake_get_supabase

    app.dependency_overrides[get_supabase] = lambda: mock_sb
    try:
        with patch(
            "stripe.Webhook.construct_event",
            return_value=VALID_SUBSCRIPTION_CREATED,
        ):
            response = await client.post(
                "/webhooks/stripe",
                content=json.dumps(VALID_SUBSCRIPTION_CREATED),
                headers={
                    "stripe-signature": "valid",
                    "content-type": "application/json",
                },
            )
    finally:
        app.dependency_overrides[get_supabase] = fake_get_supabase

    assert response.json().get("status") == "already_processed"
    # stripe_events.insert() must NOT have been called
    insert_mock.execute.assert_not_called()
