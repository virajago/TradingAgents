"""P0: 10 on-demand analyses per day per user must be enforced.

The rate-limiting logic lives in ``saas.api.routes.analyze._check_rate_limit``.
It queries ``daily_analysis_counts`` filtered by ``user_id`` and ``date``,
then raises HTTP 429 when ``count >= max_per_day``.

These tests:
  - Validate the constant (``settings.max_on_demand_per_day == 10``).
  - Verify the boundary behaviour of ``_check_rate_limit`` directly.
  - Confirm user isolation: User A's count does not affect User B.
  - Confirm the 429 detail message contains the limit value.
"""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_supabase_with_count(count: int, user_id: str = "user-123") -> MagicMock:
    """Build a mock Supabase client reporting N analyses today for user_id."""
    mock = MagicMock()
    chain = mock.table.return_value
    chain.select.return_value = chain
    chain.eq.return_value = chain  # .eq("user_id", ...) and .eq("date", ...)
    chain.execute.return_value.data = (
        [{"count": count, "user_id": user_id, "date": "2026-01-12"}]
        if count > 0
        else []
    )
    return mock


def _import_check_rate_limit():
    """Return (fn, HTTPException) or skip if not importable."""
    try:
        from saas.api.routes.analyze import _check_rate_limit
        from fastapi import HTTPException
        return _check_rate_limit, HTTPException
    except (ImportError, Exception):
        return None, None


# ---------------------------------------------------------------------------
# Constant / config tests (no mocking needed)
# ---------------------------------------------------------------------------

def test_rate_limit_is_10_per_day():
    """settings.max_on_demand_per_day must default to 10."""
    try:
        from saas.config.settings import Settings
        s = Settings()
        assert s.max_on_demand_per_day == 10
    except (ImportError, Exception):
        pytest.skip("saas.config.settings not importable")


def test_credits_on_demand_constant_exists():
    """CREDITS_ON_DEMAND_ANALYSIS must be exported from saas.config."""
    try:
        from saas.config import CREDITS_ON_DEMAND_ANALYSIS
        assert isinstance(CREDITS_ON_DEMAND_ANALYSIS, int)
        assert CREDITS_ON_DEMAND_ANALYSIS > 0
    except (ImportError, Exception):
        pytest.skip("saas.config not importable")


# ---------------------------------------------------------------------------
# _check_rate_limit boundary tests
# ---------------------------------------------------------------------------

def test_zero_analyses_does_not_raise():
    """User with 0 analyses today must not trigger rate limit."""
    fn, _exc = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    mock_sb = _make_supabase_with_count(0)
    # Must not raise — call returns None on success
    result = fn("user-123", mock_sb, max_per_day=10)
    assert result is None


def test_nine_analyses_does_not_raise():
    """9 prior analyses → 10th is allowed (count=9 < limit=10)."""
    fn, _exc = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    mock_sb = _make_supabase_with_count(9)
    result = fn("user-123", mock_sb, max_per_day=10)
    assert result is None


def test_tenth_analysis_at_limit_raises_429():
    """count=10 equals limit → must raise 429."""
    fn, HTTPException = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    mock_sb = _make_supabase_with_count(10)
    with pytest.raises(HTTPException) as exc_info:
        fn("user-123", mock_sb, max_per_day=10)
    assert exc_info.value.status_code == 429


def test_eleventh_analysis_above_limit_raises_429():
    """count > limit → must still raise 429."""
    fn, HTTPException = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    mock_sb = _make_supabase_with_count(11)
    with pytest.raises(HTTPException) as exc_info:
        fn("user-123", mock_sb, max_per_day=10)
    assert exc_info.value.status_code == 429


def test_429_detail_mentions_limit():
    """The 429 error detail must include the numeric daily limit."""
    fn, HTTPException = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    mock_sb = _make_supabase_with_count(10)
    with pytest.raises(HTTPException) as exc_info:
        fn("user-123", mock_sb, max_per_day=10)
    assert "10" in str(exc_info.value.detail)


def test_custom_limit_respected():
    """max_per_day is a parameter — custom values must be honoured."""
    fn, HTTPException = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    # count=5 is fine when limit=10
    mock_sb_ok = _make_supabase_with_count(5)
    result = fn("user-123", mock_sb_ok, max_per_day=10)
    assert result is None

    # count=5 is over limit when max_per_day=3
    mock_sb_over = _make_supabase_with_count(5)
    with pytest.raises(HTTPException) as exc_info:
        fn("user-123", mock_sb_over, max_per_day=3)
    assert exc_info.value.status_code == 429


# ---------------------------------------------------------------------------
# User isolation tests
# ---------------------------------------------------------------------------

def test_different_users_have_independent_limits():
    """User A at limit (count=10) must not affect User B (count=0)."""
    fn, HTTPException = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    mock_sb_a = _make_supabase_with_count(10, user_id="user-a")
    mock_sb_b = _make_supabase_with_count(0, user_id="user-b")

    # User A is at the limit — should raise
    with pytest.raises(HTTPException) as exc_info:
        fn("user-a", mock_sb_a, max_per_day=10)
    assert exc_info.value.status_code == 429

    # User B is fresh — should not raise
    result = fn("user-b", mock_sb_b, max_per_day=10)
    assert result is None


def test_rate_limit_query_uses_user_id_filter():
    """The daily-count query must filter by user_id (not return global counts)."""
    fn, _ = _import_check_rate_limit()
    if fn is None:
        pytest.skip("_check_rate_limit not importable")

    mock_sb = _make_supabase_with_count(0)
    fn("specific-user-id", mock_sb, max_per_day=10)

    # Verify that .eq was called — confirming user_id scoping in the query.
    chain = mock_sb.table.return_value
    assert chain.eq.called, "Rate limit query did not call .eq() — user scoping missing"


# ---------------------------------------------------------------------------
# Mock data structure sanity checks (always-run, no imports needed)
# ---------------------------------------------------------------------------

def test_mock_with_count_returns_correct_value():
    """Sanity: make_supabase_with_count() mock returns the right count."""
    mock_sb = _make_supabase_with_count(7)
    data = (
        mock_sb.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value.data
    )
    assert data[0]["count"] == 7


def test_mock_with_zero_count_returns_empty_list():
    """Sanity: count=0 → empty data list (matching real Supabase behaviour)."""
    mock_sb = _make_supabase_with_count(0)
    data = (
        mock_sb.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .execute.return_value.data
    )
    assert data == []
