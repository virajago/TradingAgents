"""FastAPI dependency providers for auth and Supabase client."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import Client, create_client

from saas.config.settings import get_settings

logger = logging.getLogger(__name__)

_bearer = HTTPBearer()


def get_supabase() -> Client:
    """Return a Supabase client using the service-role key (server-side, bypasses RLS)."""
    settings = get_settings()
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


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
