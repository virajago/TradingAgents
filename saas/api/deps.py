"""FastAPI dependency providers for auth and Supabase client."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from saas.config.settings import Settings, get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer()


def get_settings_dep() -> Settings:
    """FastAPI dependency: return application settings."""
    return get_settings()


def get_supabase() -> Client:
    """Return a Supabase client using the service-role key (server-side, bypasses RLS)."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def verify_internal_secret(
    x_internal_secret: str = Header(...),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Protect /internal/* routes — called by Cloud Scheduler only."""
    if x_internal_secret != settings.internal_api_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    supabase: Client = Depends(get_supabase),
) -> dict:
    """Validate the Bearer JWT and return the user dict from Supabase auth."""
    token = credentials.credentials
    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            )
        return {"id": str(response.user.id), "email": response.user.email}
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Auth token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        ) from exc
