"""SaaS application settings loaded from environment variables."""
from __future__ import annotations

import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)


class Settings:
    """Application settings. All values come from environment variables."""

    def __init__(self) -> None:
        self.supabase_url: str = os.environ.get("SUPABASE_URL", "")
        self.supabase_anon_key: str = os.environ.get("SUPABASE_ANON_KEY", "")
        self.supabase_service_role_key: str = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
        self.secret_key: str = os.environ.get("SECRET_KEY", "change-me-in-production")

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
