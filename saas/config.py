from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    database_url: str  # Postgres connection string via Supavisor

    # Stripe — credit pack pricing (3 products)
    stripe_secret_key: str
    stripe_webhook_secret: str
    stripe_price_starter: str = ""   # $19/month, 100 credits
    stripe_price_pro: str = ""       # $39/month, 300 credits
    stripe_price_unlimited: str = "" # $79/month, 10 000 credits
    stripe_trial_days: int = 7
    stripe_trial_credits: int = 50   # credits granted on trial start

    # Resend
    resend_api_key: str
    resend_from_email: str = "weekly@aianalystweekly.com"

    # LLM (via Cloudflare AI Gateway)
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_api_key: str = ""
    deepseek_api_key: str = ""
    cf_ai_gateway_url: str = ""  # Cloudflare AI Gateway base URL

    # Loops.so lifecycle emails
    loops_api_key: str = ""

    # Finnhub
    finnhub_api_key: str = ""

    # App
    internal_api_secret: str  # For /internal/* routes
    environment: str = "development"
    max_concurrent_analyses: int = 20
    max_on_demand_per_day: int = 10

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# ---------------------------------------------------------------------------
# Credit costs — authoritative constants shared across the codebase
# ---------------------------------------------------------------------------

CREDITS_ON_DEMAND_ANALYSIS = 10      # single ticker on-demand run
CREDITS_WEEKLY_DIGEST_PER_TICKER = 3 # Sunday digest charge per ticker
CREDITS_ALERT = 1                    # fast single-agent red flag alert
CREDITS_PORTFOLIO_AWARE_ADDON = 2    # additional cost when portfolio mode is on

# Monthly credits granted per plan on subscription renewal or creation
PLAN_CREDITS: dict[str, int] = {
    "starter": 100,
    "pro": 300,
    "unlimited": 10_000,
}
