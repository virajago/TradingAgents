"""Auth-adjacent routes — Stripe checkout session creation."""
import logging

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from supabase import Client

from saas.api.deps import get_current_user, get_settings_dep, get_supabase
from saas.config import Settings

router = APIRouter()
logger = logging.getLogger(__name__)

PLAN_PRICE_MAP = {
    "starter": "stripe_price_starter",
    "pro": "stripe_price_pro",
    "unlimited": "stripe_price_unlimited",
}


class CheckoutRequest(BaseModel):
    plan: str = "pro"
    success_url: str
    cancel_url: str


@router.post("/checkout")
async def create_checkout_session(
    body: CheckoutRequest,
    user: dict = Depends(get_current_user),
    settings: Settings = Depends(get_settings_dep),
    supabase: Client = Depends(get_supabase),
):
    """
    Create a Stripe Checkout session for a new subscription.
    Called by signup.html immediately after Supabase account creation.
    Returns a checkout_url the frontend redirects to.
    """
    if body.plan not in PLAN_PRICE_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    price_id = getattr(settings, PLAN_PRICE_MAP[body.plan], None)
    if not price_id:
        raise HTTPException(status_code=500, detail=f"Stripe price not configured for plan: {body.plan}")

    stripe.api_key = settings.stripe_secret_key

    # Get or create Stripe customer
    profile = supabase.table("profiles").select("stripe_customer_id, email").eq(
        "id", user["id"]
    ).single().execute()

    customer_id = profile.data.get("stripe_customer_id") if profile.data else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=user["email"],
            metadata={"supabase_user_id": user["id"]},
        )
        customer_id = customer["id"]
        supabase.table("profiles").update({"stripe_customer_id": customer_id}).eq(
            "id", user["id"]
        ).execute()

    try:
        session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            subscription_data={
                "trial_period_days": settings.stripe_trial_days,
                "metadata": {"supabase_user_id": user["id"], "plan": body.plan},
            },
            success_url=body.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=body.cancel_url,
            allow_promotion_codes=True,
        )
    except stripe.error.StripeError as e:
        logger.error(f"Stripe checkout session creation failed: {e}")
        raise HTTPException(status_code=502, detail="Payment provider error. Please try again.")

    return {"checkout_url": session.url, "session_id": session.id}


@router.get("/me")
async def get_current_user_profile(
    user: dict = Depends(get_current_user),
    supabase: Client = Depends(get_supabase),
):
    """Return the current user's profile including subscription status and credit balance."""
    profile = supabase.table("profiles").select("*").eq("id", user["id"]).single().execute()
    credits = supabase.table("user_credits").select("balance, lifetime_earned").eq(
        "user_id", user["id"]
    ).single().execute()

    return {
        "user": user,
        "profile": profile.data or {},
        "credits": credits.data or {"balance": 0, "lifetime_earned": 0},
    }
