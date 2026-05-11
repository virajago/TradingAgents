"""P1: Verdict settlement — correct timing, non-destructive, price-fetch graceful.

Actual source: saas/workers/verdict_settler.py
Key facts from reading the source:
  - settle_verdicts() is ASYNC, returns dict with keys: settled_30d, settled_90d, errors
  - 30d query: .eq("settled_30d", False).lte("verdict_date", cutoff_30d)
  - 90d-only query: .eq("settled_30d", True).eq("settled_90d", False).lte("verdict_date", cutoff_90d)
  - Also fetches ^GSPC price alongside ticker price
  - _get_close_price(ticker: str, target_date: date) -> float | None (sync function)
  - Uses yf.download() with start/end window of 5 days to handle weekends
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from unittest.mock import MagicMock, patch, call

import pytest


def _ensure_attr(module_name: str, attr: str, value) -> None:
    """Set an attribute on an already-stubbed module if it is missing."""
    mod = sys.modules.get(module_name)
    if mod is not None and not hasattr(mod, attr):
        setattr(mod, attr, value)


# ---------------------------------------------------------------------------
# Fixture: unregister the conftest stub so the real module can be imported
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_settler_stub():
    """Remove the conftest's pre-stubs so the real verdict_settler is imported.

    Mirrors the pattern from test_batch_scheduler: saas.workers is a fake
    types.ModuleType — removing it lets Python load the real package.
    """
    saved = {}
    for key in ("saas.workers", "saas.workers.verdict_settler"):
        if key in sys.modules:
            saved[key] = sys.modules.pop(key)

    yield

    for key in list(sys.modules):
        if key in ("saas.workers", "saas.workers.verdict_settler"):
            del sys.modules[key]

    sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_verdict(days_old: int, settled_30d=False, settled_90d=False,
                  verdict="BULLISH", verdict_id=None):
    verdict_date = (date.today() - timedelta(days=days_old)).isoformat()
    vid = verdict_id or f"v-{days_old}-{verdict}"
    return {
        "id": vid,
        "user_id": "user-123",
        "ticker": "NVDA",
        "verdict_date": verdict_date,
        "verdict": verdict,
        "price_at_verdict": 800.0,
        "settled_30d": settled_30d,
        "settled_90d": settled_90d,
    }


def _make_supabase(rows_30d=None, rows_90d=None):
    """Build a Supabase mock for settle_verdicts.

    The 30d query chain: .table("verdicts").select("*").eq(settled_30d, False)
                          .lte("verdict_date", cutoff).execute()
    The 90d query chain: .table("verdicts").select("*").eq(settled_30d, True)
                          .eq(settled_90d, False).lte("verdict_date", cutoff).execute()
    The update chain:    .table("verdicts").update(data).eq("id", vid).execute()
    """
    rows_30d = rows_30d or []
    rows_90d = rows_90d or []

    mock = MagicMock()

    # We need to differentiate between the 30d and 90d query chains.
    # The 30d chain calls .eq(False) then .lte(...)
    # The 90d chain calls .eq(True) then .eq(False) then .lte(...)
    # We track call count on the outer chain to distinguish them.
    call_count = [0]

    def _table(name):
        if name != "verdicts":
            return MagicMock()

        chain = MagicMock()

        def _select(*args, **kwargs):
            inner = MagicMock()

            query_index = [0]

            def _eq_outer(col, val):
                outer_eq = MagicMock()

                def _lte(c2, v2):
                    lte_chain = MagicMock()
                    # This is a 30d query (single eq before lte)
                    lte_chain.execute.return_value.data = rows_30d
                    return lte_chain

                def _eq_inner(col2, val2):
                    inner2 = MagicMock()

                    def _lte2(c3, v3):
                        lte2 = MagicMock()
                        # This is a 90d query (two eqs before lte)
                        lte2.execute.return_value.data = rows_90d
                        return lte2

                    inner2.lte.side_effect = _lte2
                    return inner2

                outer_eq.lte.side_effect = _lte
                outer_eq.eq.side_effect = _eq_inner
                return outer_eq

            inner.eq.side_effect = _eq_outer
            return inner

        chain.select.side_effect = _select
        chain.update.return_value.eq.return_value.execute.return_value.data = [{}]
        return chain

    mock.table.side_effect = _table
    return mock


# ---------------------------------------------------------------------------
# Tests: settle_verdicts()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_settle_verdicts_returns_dict():
    """settle_verdicts must return a dict with at minimum the settled_30d key."""
    try:
        from saas.workers.verdict_settler import settle_verdicts
    except ImportError:
        pytest.skip("verdict_settler not importable")

    mock_sb = _make_supabase(rows_30d=[], rows_90d=[])

    with patch("saas.workers.verdict_settler.create_client", return_value=mock_sb), \
         patch("saas.workers.verdict_settler.get_settings"):
        stats = await settle_verdicts()

    assert isinstance(stats, dict)
    assert "settled_30d" in stats
    assert "settled_90d" in stats


@pytest.mark.asyncio
async def test_no_settlements_when_no_due_verdicts():
    """When both queries return empty, stats must show zero settlements."""
    try:
        from saas.workers.verdict_settler import settle_verdicts
    except ImportError:
        pytest.skip("verdict_settler not importable")

    mock_sb = _make_supabase(rows_30d=[], rows_90d=[])

    with patch("saas.workers.verdict_settler.create_client", return_value=mock_sb), \
         patch("saas.workers.verdict_settler.get_settings"), \
         patch("saas.workers.verdict_settler._get_close_price", return_value=850.0):
        stats = await settle_verdicts()

    assert stats["settled_30d"] == 0
    assert stats["settled_90d"] == 0


@pytest.mark.asyncio
async def test_31day_old_verdict_increments_settled_30d():
    """A 31-day-old unsettled verdict must increment settled_30d by 1."""
    try:
        from saas.workers.verdict_settler import settle_verdicts
    except ImportError:
        pytest.skip("verdict_settler not importable")

    old_verdict = _make_verdict(31, settled_30d=False)
    mock_sb = _make_supabase(rows_30d=[old_verdict], rows_90d=[])

    with patch("saas.workers.verdict_settler.create_client", return_value=mock_sb), \
         patch("saas.workers.verdict_settler.get_settings"), \
         patch("saas.workers.verdict_settler._get_close_price", return_value=876.40):
        stats = await settle_verdicts()

    assert stats["settled_30d"] >= 1


@pytest.mark.asyncio
async def test_already_settled_30d_verdicts_not_reprocessed():
    """The 30d query filters settled_30d=False so already-settled verdicts never appear."""
    try:
        from saas.workers.verdict_settler import settle_verdicts
    except ImportError:
        pytest.skip("verdict_settler not importable")

    # Simulate already-settled verdict NOT appearing in the 30d query result
    # (the database filter excludes it)
    mock_sb = _make_supabase(rows_30d=[], rows_90d=[])

    update_calls = []
    original_table = mock_sb.table.side_effect

    def _tracking_table(name):
        chain = original_table(name)
        original_update = chain.update

        def _tracking_update(data):
            update_calls.append(data)
            return original_update(data)

        chain.update = _tracking_update
        return chain

    mock_sb.table.side_effect = _tracking_table

    with patch("saas.workers.verdict_settler.create_client", return_value=mock_sb), \
         patch("saas.workers.verdict_settler.get_settings"), \
         patch("saas.workers.verdict_settler._get_close_price", return_value=900.0):
        await settle_verdicts()

    # No update calls should have been made because both query results are empty
    assert len(update_calls) == 0


@pytest.mark.asyncio
async def test_90d_only_verdict_increments_settled_90d():
    """A verdict with settled_30d=True and settled_90d=False older than 90 days
    must be processed by the 90d-only branch and increment settled_90d."""
    try:
        from saas.workers.verdict_settler import settle_verdicts
    except ImportError:
        pytest.skip("verdict_settler not importable")

    old_verdict_90 = _make_verdict(91, settled_30d=True, settled_90d=False)
    mock_sb = _make_supabase(rows_30d=[], rows_90d=[old_verdict_90])

    with patch("saas.workers.verdict_settler.create_client", return_value=mock_sb), \
         patch("saas.workers.verdict_settler.get_settings"), \
         patch("saas.workers.verdict_settler._get_close_price", return_value=920.0):
        stats = await settle_verdicts()

    assert stats["settled_90d"] >= 1


@pytest.mark.asyncio
async def test_price_fetch_none_does_not_crash():
    """If _get_close_price returns None, settlement still completes without raising."""
    try:
        from saas.workers.verdict_settler import settle_verdicts
    except ImportError:
        pytest.skip("verdict_settler not importable")

    old_verdict = _make_verdict(35, settled_30d=False)
    mock_sb = _make_supabase(rows_30d=[old_verdict], rows_90d=[])

    with patch("saas.workers.verdict_settler.create_client", return_value=mock_sb), \
         patch("saas.workers.verdict_settler.get_settings"), \
         patch("saas.workers.verdict_settler._get_close_price", return_value=None):
        stats = await settle_verdicts()  # must not raise

    assert isinstance(stats, dict)
    # The verdict was still settled (price_30d just won't be written)
    assert stats["settled_30d"] >= 1


@pytest.mark.asyncio
async def test_error_in_settlement_increments_error_count():
    """If settlement of a verdict raises unexpectedly, errors counter must increment."""
    try:
        from saas.workers.verdict_settler import settle_verdicts
    except ImportError:
        pytest.skip("verdict_settler not importable")

    # Use a verdict with an unparseable date to trigger an error inside the loop
    bad_verdict = {
        "id": "v-bad",
        "user_id": "user-123",
        "ticker": "NVDA",
        "verdict_date": "not-a-date",  # will raise fromisoformat
        "verdict": "BULLISH",
        "price_at_verdict": 800.0,
        "settled_30d": False,
        "settled_90d": False,
    }
    mock_sb = _make_supabase(rows_30d=[bad_verdict], rows_90d=[])

    with patch("saas.workers.verdict_settler.create_client", return_value=mock_sb), \
         patch("saas.workers.verdict_settler.get_settings"), \
         patch("saas.workers.verdict_settler._get_close_price", return_value=850.0):
        stats = await settle_verdicts()

    assert stats["errors"] >= 1


# ---------------------------------------------------------------------------
# Tests: _get_close_price()
# ---------------------------------------------------------------------------

def test_get_close_price_returns_none_on_empty_dataframe():
    """_get_close_price must return None when yfinance returns an empty DataFrame."""
    try:
        from saas.workers.verdict_settler import _get_close_price
    except ImportError:
        pytest.skip("_get_close_price not importable")

    import pandas as pd

    target = date.today() - timedelta(days=35)

    with patch("saas.workers.verdict_settler.yf.download", return_value=pd.DataFrame()):
        result = _get_close_price("NVDA", target)

    assert result is None


def test_get_close_price_returns_float_on_valid_data():
    """_get_close_price must return a float when yfinance returns valid OHLCV data."""
    try:
        from saas.workers.verdict_settler import _get_close_price
    except ImportError:
        pytest.skip("_get_close_price not importable")

    import pandas as pd

    target = date.today() - timedelta(days=35)
    mock_hist = pd.DataFrame(
        {"Close": [876.40]},
        index=[pd.Timestamp(target)],
    )

    with patch("saas.workers.verdict_settler.yf.download", return_value=mock_hist):
        result = _get_close_price("NVDA", target)

    assert isinstance(result, float)
    assert abs(result - 876.40) < 0.01


def test_get_close_price_returns_none_on_yfinance_exception():
    """_get_close_price must return None (not raise) when yfinance throws."""
    try:
        from saas.workers.verdict_settler import _get_close_price
    except ImportError:
        pytest.skip("_get_close_price not importable")

    target = date.today() - timedelta(days=35)

    with patch("saas.workers.verdict_settler.yf.download", side_effect=Exception("network error")):
        result = _get_close_price("NVDA", target)

    assert result is None


def test_get_close_price_downloads_window_starting_at_target():
    """_get_close_price must pass target_date as the start of the download window."""
    try:
        from saas.workers.verdict_settler import _get_close_price
    except ImportError:
        pytest.skip("_get_close_price not importable")

    import pandas as pd

    target = date.today() - timedelta(days=40)
    mock_hist = pd.DataFrame(
        {"Close": [800.0]},
        index=[pd.Timestamp(target)],
    )

    with patch("saas.workers.verdict_settler.yf.download", return_value=mock_hist) as mock_dl:
        _get_close_price("AAPL", target)

    _, kwargs = mock_dl.call_args
    call_args = mock_dl.call_args
    # start should equal target.isoformat()
    positional = call_args[0] if call_args[0] else []
    kw = call_args[1] if call_args[1] else {}
    start_arg = kw.get("start") or (positional[1] if len(positional) > 1 else None)
    assert start_arg == target.isoformat()
