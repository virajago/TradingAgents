"""Stripe webhook handler with idempotency."""
import logging

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from supabase import Client

from saas.api.deps import get_settings_dep, get_supabase
from saas.config import PLAN_CREDITS, Settings

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_plan_from_price(price_id: str, settings: Settings) -> str:
    """Map a Stripe price ID to an internal plan name."""
    if price_id == settings.stripe_price_starter:
        return "starter"
    if price_id == settings.stripe_price_pro:
        return "pro"
    if price_id == settings.stripe_price_unlimited:
        return "unlimited"
    # Fall back gracefully — log so ops can catch a misconfigured price ID
    logger.warning("Unknown Stripe price ID %s; defaulting plan to 'starter'", price_id)
    return "starter"


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(..., alias="stripe-signature"),
    settings: Settings = Depends(get_settings_dep),
    supabase: Client = Depends(get_supabase),
) -> dict:
    payload = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.stripe_webhook_secret
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Idempotency: skip already-processed events
    existing = (
        supabase.table("stripe_events")
        .select("event_id")
        .eq("event_id", event["id"])
        .execute()
    )
    if existing.data:
        return {"status": "already_processed"}

    try:
        sub = event["data"]["object"]
        if event["type"] == "customer.subscription.created":
            _handle_subscription_created(sub, supabase, settings)
            # Grant trial credits if the subscription starts in trial
            if sub.get("status") == "trialing":
                _handle_trial_started(sub, supabase, settings)
        elif event["type"] == "customer.subscription.deleted":
            _handle_subscription_deleted(sub, supabase)
        elif event["type"] == "customer.subscription.updated":
            _handle_subscription_updated(sub, supabase, settings)
        elif event["type"] == "invoice.payment_failed":
            _handle_payment_failed(sub, supabase)
        elif event["type"] == "invoice.payment_succeeded":
            _handle_payment_succeeded(sub, supabase, settings)
        else:
            logger.debug("Unhandled Stripe event type: %s", event["type"])
    except Exception:
        logger.exception("Error processing Stripe event %s (%s)", event["id"], event["type"])
        raise HTTPException(status_code=500, detail="Webhook processing error")

    # Mark as processed only after successful handling
    supabase.table("stripe_events").insert({"event_id": event["id"]}).execute()
    return {"status": "processed"}


def _resolve_user_id(customer_id: str, supabase: Client) -> str | None:
    """Look up the internal user_id for a Stripe customer ID."""
    result = (
        supabase.table("profiles")
        .select("id")
        .eq("stripe_customer_id", customer_id)
        .execute()
    )
    if result.data:
        return result.data[0]["id"]
    logger.warning("No profile found for Stripe customer %s", customer_id)
    return None


def _handle_subscription_created(
    sub: dict, supabase: Client, settings: Settings
) -> None:
    customer_id = sub["customer"]
    price_id = sub["items"]["data"][0]["price"]["id"]
    plan = _get_plan_from_price(price_id, settings)
    credits = PLAN_CREDITS[plan]

    user_id = _resolve_user_id(customer_id, supabase)
    if not user_id:
        return

    supabase.table("profiles").update(
        {
            "stripe_subscription_id": sub["id"],
            "subscription_status": "active",
            "plan_name": plan,
        }
    ).eq("id", user_id).execute()

    # Grant monthly credits (non-trial subscriptions start immediately)
    if sub.get("status") != "trialing":
        supabase.rpc(
            "grant_credits",
            {
                "p_user_id": user_id,
                "p_amount": credits,
                "p_action": "subscription_renewal",
                "p_reference_id": sub["id"],
            },
        ).execute()


def _handle_trial_started(
    sub: dict, supabase: Client, settings: Settings
) -> None:
    """Grant 50 trial credits when a trial subscription is created."""
    user_id = _resolve_user_id(sub["customer"], supabase)
    if not user_id:
        return

    supabase.rpc(
        "grant_credits",
        {
            "p_user_id": user_id,
            "p_amount": settings.stripe_trial_credits,
            "p_action": "trial_grant",
            "p_reference_id": sub["id"],
        },
    ).execute()


def _handle_subscription_deleted(sub: dict, supabase: Client) -> None:
    supabase.table("profiles").update(
        {"subscription_status": "canceled"}
    ).eq("stripe_subscription_id", sub["id"]).execute()


def _handle_subscription_updated(
    sub: dict, supabase: Client, settings: Settings
) -> None:
    status_map = {
        "active": "active",
        "past_due": "past_due",
        "canceled": "canceled",
        "unpaid": "past_due",
        "trialing": "active",
    }
    new_status = status_map.get(sub["status"], "inactive")

    # Also sync plan_name in case the customer switched tiers
    price_id = sub["items"]["data"][0]["price"]["id"]
    plan = _get_plan_from_price(price_id, settings)

    supabase.table("profiles").update(
        {"subscription_status": new_status, "plan_name": plan}
    ).eq("stripe_subscription_id", sub["id"]).execute()


def _handle_payment_succeeded(
    invoice: dict, supabase: Client, settings: Settings
) -> None:
    """Grant plan credits on each successful renewal invoice."""
    # Only process recurring subscription invoices (billing_reason = 'subscription_cycle')
    if invoice.get("billing_reason") not in ("subscription_cycle", "subscription_create"):
        return

    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return

    result = (
        supabase.table("profiles")
        .select("id, plan_name")
        .eq("stripe_subscription_id", subscription_id)
        .execute()
    )
    if not result.data:
        return

    user_id = result.data[0]["id"]
    plan = result.data[0].get("plan_name", "starter")
    credits = PLAN_CREDITS.get(plan, PLAN_CREDITS["starter"])

    supabase.rpc(
        "grant_credits",
        {
            "p_user_id": user_id,
            "p_amount": credits,
            "p_action": "subscription_renewal",
            "p_reference_id": invoice.get("id"),
        },
    ).execute()


def _handle_payment_failed(invoice: dict, supabase: Client) -> None:
    supabase.table("profiles").update(
        {"subscription_status": "past_due"}
    ).eq("stripe_customer_id", invoice["customer"]).execute()
