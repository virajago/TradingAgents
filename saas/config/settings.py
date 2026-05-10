"""SaaS application settings loaded from environment variables."""
from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings:
    """Application settings. All values come from environment variables."""

    def __init__(self) -> None:
        # Supabase
        self.supabase_url: str = os.environ.get("SUPABASE_URL", "")
        self.supabase_anon_key: str = os.environ.get("SUPABASE_ANON_KEY", "")
        self.supabase_service_role_key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.supabase_jwt_secret: str = os.environ.get("SUPABASE_JWT_SECRET", "")
        self.database_url: str = os.environ.get("DATABASE_URL", "")

        # Stripe
        self.stripe_secret_key: str = os.environ.get("STRIPE_SECRET_KEY", "")
        self.stripe_webhook_secret: str = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
        self.stripe_price_starter: str = os.environ.get("STRIPE_PRICE_STARTER", "")
        self.stripe_price_pro: str = os.environ.get("STRIPE_PRICE_PRO", "")
        self.stripe_price_unlimited: str = os.environ.get("STRIPE_PRICE_UNLIMITED", "")
        self.stripe_trial_days: int = int(os.environ.get("STRIPE_TRIAL_DAYS", "7"))
        self.stripe_trial_credits: int = int(os.environ.get("STRIPE_TRIAL_CREDITS", "50"))

        # Resend
        self.resend_api_key: str = os.environ.get("RESEND_API_KEY", "")
        self.resend_from_email: str = os.environ.get(
            "RESEND_FROM_EMAIL", "weekly@aianalystweekly.com"
        )

        # LLM (via Cloudflare AI Gateway)
        self.openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")
        self.anthropic_api_key: str = os.environ.get("ANTHROPIC_API_KEY", "")
        self.google_api_key: str = os.environ.get("GOOGLE_API_KEY", "")
        self.deepseek_api_key: str = os.environ.get("DEEPSEEK_API_KEY", "")
        self.cf_ai_gateway_url: str = os.environ.get("CF_AI_GATEWAY_URL", "")

        # Loops.so lifecycle emails
        self.loops_api_key: str = os.environ.get("LOOPS_API_KEY", "")

        # LLM model config — two-tier cost strategy
        self.analyst_provider: str = os.environ.get("ANALYST_PROVIDER", "google")
        self.analyst_model: str = os.environ.get("ANALYST_MODEL", "gemini-2.5-flash")
        self.synthesis_provider: str = os.environ.get("SYNTHESIS_PROVIDER", "anthropic")
        self.synthesis_model: str = os.environ.get("SYNTHESIS_MODEL", "claude-sonnet-4-6")

        # Finnhub
        self.finnhub_api_key: str = os.environ.get("FINNHUB_API_KEY", "")

        # App
        self.secret_key: str = os.environ.get("SECRET_KEY", "change-me-in-production")
        self.internal_api_secret: str = os.environ.get("INTERNAL_API_SECRET", "")
        self.environment: str = os.environ.get("ENVIRONMENT", "development")
        self.max_concurrent_analyses: int = int(
            os.environ.get("MAX_CONCURRENT_ANALYSES", "20")
        )
        self.max_on_demand_per_day: int = int(os.environ.get("MAX_ON_DEMAND_PER_DAY", "10"))

    def validate(self) -> None:
        """Raise if required settings are missing."""
        missing = [
            name
            for name, val in [
                ("SUPABASE_URL", self.supabase_url),
                ("SUPABASE_ANON_KEY", self.supabase_anon_key),
                ("SUPABASE_SERVICE_ROLE_KEY", self.supabase_service_role_key),
            ]
            if not val
        ]
        if missing:
            raise RuntimeError(f"Missing required env vars: {', '.join(missing)}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
