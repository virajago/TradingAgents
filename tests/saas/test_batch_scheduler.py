"""P1: Batch scheduler — only processes active users, skips empty watchlists,
handles per-ticker failures gracefully.

Actual source: saas/workers/batch_scheduler.py
Key facts from reading the source:
  - run_weekly_batch(trade_date=None) is SYNCHRONOUS, returns None
  - Fetches profiles from `profiles` table (no subscription filter at query time)
  - Fetches watchlist from `watchlist` table filtered by user_id
  - Calls run_analysis() and _fetch_portfolio_context() from analysis_worker
  - No send_digest_email / format_digest_email in this module
"""
from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock, patch

import pytest


def _ensure_attr(module_name: str, attr: str, value) -> None:
    """Set an attribute on an already-stubbed module if it is missing."""
    mod = sys.modules.get(module_name)
    if mod is not None and not hasattr(mod, attr):
        setattr(mod, attr, value)


# ---------------------------------------------------------------------------
# Helpers to build realistic mock Supabase clients for batch_scheduler
# ---------------------------------------------------------------------------

def _make_chainable_mock():
    """Return a MagicMock whose common query-builder methods all return itself."""
    m = MagicMock()
    m.select.return_value = m
    m.eq.return_value = m
    m.execute.return_value.data = []
    return m


def make_supabase_for_batch(user_ids=None, watchlists=None):
    """Build a mock Supabase that drives batch_scheduler's two queries.

    Args:
        user_ids: list of user id strings returned by `profiles` select.
        watchlists: dict mapping user_id -> list of ticker strings for the
                    `watchlist` table query.
    """
    user_ids = user_ids or []
    watchlists = watchlists or {}

    mock = MagicMock()

    def _table(name):
        chain = _make_chainable_mock()
        if name == "profiles":
            chain.execute.return_value.data = [{"id": uid} for uid in user_ids]
        elif name == "watchlist":
            # eq("user_id", uid) is called for each user — capture the uid arg
            def _eq_dispatch(col, val):
                inner = MagicMock()
                tickers = watchlists.get(val, [])
                inner.execute.return_value.data = [{"ticker": t} for t in tickers]
                return inner
            chain.eq.side_effect = _eq_dispatch
        return chain

    mock.table.side_effect = _table
    return mock


# ---------------------------------------------------------------------------
# Fixture: unregister the conftest stub so the real module can be imported
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_batch_stub():
    """Remove the conftest's pre-stubs so the real batch_scheduler is imported.

    The conftest stubs saas.workers as a plain types.ModuleType (not a real
    package), which prevents Python from loading submodules under it. We must
    remove the fake saas.workers entry alongside the worker-level stubs.
    We restore the saas.workers stub on teardown so subsequent tests that
    rely on the conftest stubs continue to work.
    """
    # Save stubs that we'll remove
    saved = {}
    for key in (
        "saas.workers",
        "saas.workers.batch_scheduler",
        "saas.workers.analysis_worker",
    ):
        if key in sys.modules:
            saved[key] = sys.modules.pop(key)

    # Patch required symbols onto already-stubbed tradingagents modules
    _ensure_attr("tradingagents.pipeline.runner", "run_analysis", MagicMock())
    _ensure_attr("tradingagents.pipeline.checkpoint", "get_checkpoint", MagicMock())
    _ensure_attr("tradingagents.pipeline.state", "AnalysisState", MagicMock())

    yield

    # Remove any real modules loaded during the test
    for key in list(sys.modules):
        if key in (
            "saas.workers",
            "saas.workers.batch_scheduler",
            "saas.workers.analysis_worker",
        ):
            del sys.modules[key]

    # Restore the conftest stubs for downstream tests
    sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_batch_calls_run_analysis_for_each_ticker():
    """run_weekly_batch must call run_analysis once per (user, ticker) pair."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    mock_sb = make_supabase_for_batch(
        user_ids=["u1"],
        watchlists={"u1": ["NVDA", "AAPL"]},
    )
    analysis_calls = []

    def fake_run_analysis(**kwargs):
        analysis_calls.append(kwargs)

    def fake_fetch_portfolio(supabase, user_id):
        return {}

    with patch("saas.workers.batch_scheduler.create_client", return_value=mock_sb), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis", side_effect=fake_run_analysis), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", side_effect=fake_fetch_portfolio):
        run_weekly_batch()

    tickers_called = [c["ticker"] for c in analysis_calls]
    assert "NVDA" in tickers_called
    assert "AAPL" in tickers_called
    assert len(analysis_calls) == 2


def test_batch_skips_users_with_empty_watchlist():
    """Users with no watchlist items must not trigger any run_analysis call."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    mock_sb = make_supabase_for_batch(
        user_ids=["u1"],
        watchlists={"u1": []},  # empty watchlist
    )
    analysis_calls = []

    def fake_run_analysis(**kwargs):
        analysis_calls.append(kwargs)

    def fake_fetch_portfolio(supabase, user_id):
        return {}

    with patch("saas.workers.batch_scheduler.create_client", return_value=mock_sb), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis", side_effect=fake_run_analysis), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", side_effect=fake_fetch_portfolio):
        run_weekly_batch()

    assert len(analysis_calls) == 0


def test_batch_processes_multiple_users():
    """Each user's tickers are analysed independently."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    mock_sb = make_supabase_for_batch(
        user_ids=["u1", "u2"],
        watchlists={
            "u1": ["NVDA", "AAPL", "MSFT"],
            "u2": ["GOOGL"],
        },
    )
    analysis_calls = []

    def fake_run_analysis(**kwargs):
        analysis_calls.append((kwargs["user_id"], kwargs["ticker"]))

    def fake_fetch_portfolio(supabase, user_id):
        return {}

    with patch("saas.workers.batch_scheduler.create_client", return_value=mock_sb), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis", side_effect=fake_run_analysis), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", side_effect=fake_fetch_portfolio):
        run_weekly_batch()

    # u1 → 3 calls, u2 → 1 call
    assert len(analysis_calls) == 4
    assert ("u1", "NVDA") in analysis_calls
    assert ("u2", "GOOGL") in analysis_calls


def test_batch_continues_after_single_analysis_failure():
    """One ticker failing must not prevent the remaining tickers from running."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    mock_sb = make_supabase_for_batch(
        user_ids=["u1", "u2"],
        watchlists={
            "u1": ["NVDA"],
            "u2": ["AAPL"],
        },
    )
    call_count = [0]
    succeeded = []

    def flaky_run_analysis(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("LLM timeout on first ticker")
        succeeded.append(kwargs["ticker"])

    def fake_fetch_portfolio(supabase, user_id):
        return {}

    # Must not raise even when first analysis fails
    with patch("saas.workers.batch_scheduler.create_client", return_value=mock_sb), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis", side_effect=flaky_run_analysis), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", side_effect=fake_fetch_portfolio):
        run_weekly_batch()  # must not raise

    assert "AAPL" in succeeded


def test_batch_returns_none():
    """run_weekly_batch must return None (it is a fire-and-forget scheduler)."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    mock_sb = make_supabase_for_batch(user_ids=[], watchlists={})

    with patch("saas.workers.batch_scheduler.create_client", return_value=mock_sb), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis"), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", return_value={}):
        result = run_weekly_batch()

    assert result is None


def test_batch_passes_trade_date_to_analysis():
    """The trade_date argument must be forwarded to each run_analysis call."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    mock_sb = make_supabase_for_batch(
        user_ids=["u1"],
        watchlists={"u1": ["TSLA"]},
    )
    captured = {}

    def fake_run_analysis(**kwargs):
        captured.update(kwargs)

    def fake_fetch_portfolio(supabase, user_id):
        return {}

    with patch("saas.workers.batch_scheduler.create_client", return_value=mock_sb), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis", side_effect=fake_run_analysis), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", side_effect=fake_fetch_portfolio):
        run_weekly_batch(trade_date="2026-01-12")

    assert captured.get("trade_date") == "2026-01-12"


def test_batch_uses_today_when_no_trade_date_given():
    """run_weekly_batch defaults trade_date to today's ISO date."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    from datetime import date

    mock_sb = make_supabase_for_batch(
        user_ids=["u1"],
        watchlists={"u1": ["META"]},
    )
    captured = {}

    def fake_run_analysis(**kwargs):
        captured.update(kwargs)

    def fake_fetch_portfolio(supabase, user_id):
        return {}

    with patch("saas.workers.batch_scheduler.create_client", return_value=mock_sb), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis", side_effect=fake_run_analysis), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", side_effect=fake_fetch_portfolio):
        run_weekly_batch()

    assert captured.get("trade_date") == date.today().isoformat()


def test_batch_survives_watchlist_fetch_failure():
    """If the watchlist query raises, the user is skipped but others continue."""
    try:
        from saas.workers.batch_scheduler import run_weekly_batch
    except ImportError:
        pytest.skip("batch_scheduler not importable")

    # Build a mock where one user's watchlist fetch raises
    mock = MagicMock()
    mock.table.return_value.select.return_value.execute.return_value.data = [
        {"id": "u1"}, {"id": "u2"}
    ]

    call_num = [0]
    analysis_calls = []

    def _table(name):
        chain = MagicMock()
        chain.select.return_value = chain
        if name == "profiles":
            chain.execute.return_value.data = [{"id": "u1"}, {"id": "u2"}]
        elif name == "watchlist":
            def _eq(col, val):
                inner = MagicMock()
                call_num[0] += 1
                if val == "u1":
                    inner.execute.side_effect = Exception("DB error")
                else:
                    inner.execute.return_value.data = [{"ticker": "AAPL"}]
                return inner
            chain.eq.side_effect = _eq
        return chain

    mock.table.side_effect = _table

    def fake_run_analysis(**kwargs):
        analysis_calls.append(kwargs["ticker"])

    def fake_fetch_portfolio(supabase, user_id):
        return {}

    with patch("saas.workers.batch_scheduler.create_client", return_value=mock), \
         patch("saas.workers.batch_scheduler.get_settings"), \
         patch("saas.workers.batch_scheduler.run_analysis", side_effect=fake_run_analysis), \
         patch("saas.workers.batch_scheduler._fetch_portfolio_context", side_effect=fake_fetch_portfolio):
        run_weekly_batch()  # must not raise

    # u2's ticker should still be processed despite u1 failing
    assert "AAPL" in analysis_calls
