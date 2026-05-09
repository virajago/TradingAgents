from fastapi import Depends, HTTPException, Header, status
from supabase import create_client, Client
import jwt

from saas.config import get_settings, Settings


def get_settings_dep() -> Settings:
    return get_settings()


def get_supabase(settings: Settings = Depends(get_settings_dep)) -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


async def get_current_user(
    authorization: str = Header(...),
    settings: Settings = Depends(get_settings_dep),
) -> dict:
    """Validate Supabase JWT and return user dict with id, email."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header",
        )
    token = authorization.removeprefix("Bearer ")
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        return {"id": payload["sub"], "email": payload.get("email", "")}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


async def verify_internal_secret(
    x_internal_secret: str = Header(...),
    settings: Settings = Depends(get_settings_dep),
) -> None:
    """Protect /internal/* routes — called by Cloud Scheduler only."""
    if x_internal_secret != settings.internal_api_secret:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        )
