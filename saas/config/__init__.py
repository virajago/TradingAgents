"""SaaS configuration — re-exports Settings, get_settings, and credit constants."""
from saas.config.settings import Settings, get_settings

# ---------------------------------------------------------------------------
# Credit costs — authoritative constants shared across the codebase
# ---------------------------------------------------------------------------

CREDITS_ON_DEMAND_ANALYSIS = 10       # single ticker on-demand run
CREDITS_WEEKLY_DIGEST_PER_TICKER = 3  # Sunday digest charge per ticker
CREDITS_ALERT = 1                     # fast single-agent red flag alert
CREDITS_PORTFOLIO_AWARE_ADDON = 2     # additional cost when portfolio mode is on

# Monthly credits granted per plan on subscription renewal or creation
PLAN_CREDITS: dict[str, int] = {
    "starter": 100,
    "pro": 300,
    "unlimited": 10_000,
}

__all__ = [
    "Settings",
    "get_settings",
    "CREDITS_ON_DEMAND_ANALYSIS",
    "CREDITS_WEEKLY_DIGEST_PER_TICKER",
    "CREDITS_ALERT",
    "CREDITS_PORTFOLIO_AWARE_ADDON",
    "PLAN_CREDITS",
]
