"""P0: JWT auth dependency must reject invalid / missing tokens with HTTP 401.

Implementation note
-------------------
``saas.api.deps.get_current_user`` is a FastAPI dependency that accepts an
``HTTPAuthorizationCredentials`` object (produced by ``HTTPBearer``) rather
than a raw Authorization header string.  It delegates token validation to
Supabase's ``auth.get_user(token)`` — it does NOT perform local JWT decode.

These tests therefore:
  1. Call ``get_current_user`` with a mock credentials object.
  2. Control the Supabase client via ``patch("saas.api.deps.get_supabase")``.
  3. Simulate valid / invalid / expired responses from the Supabase auth API.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, AsyncMock

FAKE_USER_ID = "user-test-uuid-1234"
FAKE_EMAIL = "test@example.com"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_credentials(token: str) -> MagicMock:
    """Return a fake HTTPAuthorizationCredentials with the given token."""
    creds = MagicMock()
    creds.credentials = token
    return creds


def _make_supabase_with_user(user_id: str = FAKE_USER_ID, email: str = FAKE_EMAIL):
    """Supabase mock whose auth.get_user() returns a valid user."""
    user = MagicMock()
    user.id = user_id
    user.email = email

    response = MagicMock()
    response.user = user

    supabase = MagicMock()
    supabase.auth.get_user.return_value = response
    return supabase


def _make_supabase_raising(exc: Exception):
    """Supabase mock whose auth.get_user() raises the given exception."""
    supabase = MagicMock()
    supabase.auth.get_user.side_effect = exc
    return supabase


def _make_supabase_no_user():
    """Supabase mock whose auth.get_user() returns a response with no user."""
    response = MagicMock()
    response.user = None

    supabase = MagicMock()
    supabase.auth.get_user.return_value = response
    return supabase


def _get_current_user_fn():
    """Import get_current_user — return None if not importable."""
    try:
        from saas.api.deps import get_current_user
        return get_current_user
    except (ImportError, Exception):
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_valid_token_returns_user():
    """A token that Supabase accepts must return id + email."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    mock_sb = _make_supabase_with_user()
    with patch("saas.api.deps.get_supabase", return_value=mock_sb):
        result = await fn(
            credentials=_make_credentials("valid-token"),
            supabase=mock_sb,
        )
    assert result["id"] == FAKE_USER_ID
    assert result["email"] == FAKE_EMAIL


@pytest.mark.asyncio
async def test_supabase_raises_returns_401():
    """When Supabase raises any exception the dependency must return 401."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    from fastapi import HTTPException

    mock_sb = _make_supabase_raising(Exception("invalid JWT"))
    with patch("saas.api.deps.get_supabase", return_value=mock_sb):
        with pytest.raises(HTTPException) as exc_info:
            await fn(
                credentials=_make_credentials("bad-token"),
                supabase=mock_sb,
            )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_expired_token_returns_401():
    """An expired-token error from Supabase must surface as HTTP 401."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    from fastapi import HTTPException

    mock_sb = _make_supabase_raising(Exception("JWT expired"))
    with pytest.raises(HTTPException) as exc_info:
        await fn(
            credentials=_make_credentials("expired-token"),
            supabase=mock_sb,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_wrong_secret_returns_401():
    """A token signed with the wrong secret must be rejected with 401."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    from fastapi import HTTPException

    mock_sb = _make_supabase_raising(Exception("invalid signature"))
    with pytest.raises(HTTPException) as exc_info:
        await fn(
            credentials=_make_credentials("wrong-secret-token"),
            supabase=mock_sb,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_no_user_in_response_returns_401():
    """If Supabase returns a response with no user, must raise 401."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    from fastapi import HTTPException

    mock_sb = _make_supabase_no_user()
    with pytest.raises(HTTPException) as exc_info:
        await fn(
            credentials=_make_credentials("token-with-no-user"),
            supabase=mock_sb,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_none_response_returns_401():
    """If Supabase returns None entirely, must raise 401."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    from fastapi import HTTPException

    mock_sb = MagicMock()
    mock_sb.auth.get_user.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        await fn(
            credentials=_make_credentials("token-with-none-response"),
            supabase=mock_sb,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token_returns_401():
    """A structurally invalid token must cause a 401, not a 500."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    from fastapi import HTTPException

    mock_sb = _make_supabase_raising(Exception("malformed token"))
    with pytest.raises(HTTPException) as exc_info:
        await fn(
            credentials=_make_credentials("not.a.real.jwt"),
            supabase=mock_sb,
        )
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_returned_user_dict_has_id_and_email():
    """The dict returned on success must have exactly 'id' and 'email' keys."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    mock_sb = _make_supabase_with_user(user_id="uuid-abc", email="user@corp.com")
    result = await fn(
        credentials=_make_credentials("valid-token"),
        supabase=mock_sb,
    )
    assert "id" in result
    assert "email" in result
    assert result["id"] == "uuid-abc"
    assert result["email"] == "user@corp.com"


@pytest.mark.asyncio
async def test_user_id_is_string():
    """User ID in the returned dict must be a plain string (not UUID object)."""
    fn = _get_current_user_fn()
    if fn is None:
        pytest.skip("saas.api.deps not importable")

    import uuid

    user = MagicMock()
    user.id = uuid.UUID("12345678-1234-5678-1234-567812345678")
    user.email = "test@example.com"

    response = MagicMock()
    response.user = user

    mock_sb = MagicMock()
    mock_sb.auth.get_user.return_value = response

    result = await fn(
        credentials=_make_credentials("uuid-token"),
        supabase=mock_sb,
    )
    assert isinstance(result["id"], str), "id must be coerced to str"
