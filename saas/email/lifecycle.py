"""
Loops.so lifecycle email integration.
Sends events to Loops so it can trigger onboarding sequences,
trial nudges, and re-engagement campaigns without code deploys.
"""
import logging

import httpx

from saas.config import get_settings

logger = logging.getLogger(__name__)


async def track_event(email: str, event_name: str, properties: dict = {}) -> None:
    """
    Fire a Loops event. Non-blocking — errors are logged but never raised.

    Key events to fire from application code:
      trial_started         — when Stripe trial subscription is created
      first_analysis_done   — after user's first on-demand analysis completes
      credits_low           — when balance drops below 20% of plan allocation
      trial_ending_soon     — 24 hours before trial expires (fire from a cron)
      subscription_active   — when trial converts to paid
      subscription_canceled — when user cancels
    """
    settings = get_settings()
    if not settings.loops_api_key:
        return  # Loops not configured — skip silently

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "https://app.loops.so/api/v1/events/send",
                headers={
                    "Authorization": f"Bearer {settings.loops_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "email": email,
                    "eventName": event_name,
                    "eventProperties": properties,
                },
            )
    except Exception as e:
        logger.warning("Loops event '%s' failed for %s: %s", event_name, email, e)


async def sync_contact(email: str, properties: dict) -> None:
    """Create or update a contact in Loops."""
    settings = get_settings()
    if not settings.loops_api_key:
        return

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(
                "https://app.loops.so/api/v1/contacts/update",
                headers={
                    "Authorization": f"Bearer {settings.loops_api_key}",
                    "Content-Type": "application/json",
                },
                json={"email": email, **properties},
            )
    except Exception as e:
        logger.warning("Loops contact sync failed for %s: %s", email, e)
