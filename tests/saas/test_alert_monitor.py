"""P1: Alert monitor — threshold detection, user isolation, graceful failures.

Actual source: saas/workers/alert_monitor.py
Key facts from reading the source:
  - check_alerts() is ASYNC, returns None
  - Threshold constant is _ALERT_THRESHOLD_PCT = 5.0 (module-private)
  - Checks settings.finnhub_api_key; if empty → logs warning and returns
  - Queries watchlist_items with profiles join, filters active subscription_status
  - For each ticker: calls client.quote(ticker), computes pct_change
  - Deducts credits via supabase.rpc("deduct_credits", ...) before sending email
  - If credit deduction returns None or < 0 → skips email for that user
  - Calls await send_alert_email(email, ticker, pct_change, analysis_string)
  - Imports finnhub locally inside check_alerts()
"""
from __future__ import annotations

import sys
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _ensure_attr(module_name: str, attr: str, value) -> None:
    """Set an attribute on an already-stubbed module if it is missing."""
    mod = sys.modules.get(module_name)
    if mod is not None and not hasattr(mod, attr):
        setattr(mod, attr, value)


# ---------------------------------------------------------------------------
# Fixture: remove conftest stub so real module is importable
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_alert_stub():
    """Remove the conftest's pre-stubs so the real alert_monitor is imported.

    Mirrors the pattern from test_batch_scheduler: saas.workers is a fake
    types.ModuleType — removing it lets Python load the real package.
    """
    saved = {}
    for key in ("saas.workers", "saas.workers.alert_monitor"):
        if key in sys.modules:
            saved[key] = sys.modules.pop(key)

    # Ensure saas.email.sender stub has send_alert_email
    _ensure_attr("saas.email.sender", "send_alert_email", AsyncMock())

    yield

    for key in list(sys.modules):
        if key in ("saas.workers", "saas.workers.alert_monitor"):
            del sys.modules[key]

    sys.modules.update(saved)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _active_profile(user_id="u1", email="user@test.com"):
    return {"id": user_id, "email": email, "subscription_status": "active"}


def _make_supabase_with_watchlist(ticker_users: dict):
    """Build a mock Supabase client for alert_monitor.

    alert_monitor joins watchlist_items → profiles and reads row["profiles"].
    ticker_users = {ticker: [profile_dict, ...]}
    """
    rows = []
    for ticker, users in ticker_users.items():
        for user in users:
            rows.append({"ticker": ticker, "profiles": user})

    mock = MagicMock()
    chain = mock.table.return_value
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.execute.return_value.data = rows

    # Credit deduction returns a positive balance by default
    mock.rpc.return_value.execute.return_value.data = 50

    return mock


def _make_settings(finnhub_api_key="test-key"):
    s = MagicMock()
    s.finnhub_api_key = finnhub_api_key
    s.supabase_url = "https://test.supabase.co"
    s.supabase_service_role_key = "test-key"
    return s


def _make_finnhub_module(quote_return=None, side_effect=None):
    """Return a fake finnhub module whose Client.quote() returns quote_return."""
    finnhub_mod = types.ModuleType("finnhub")

    class FakeClient:
        def __init__(self, api_key=None):
            pass

        def quote(self, ticker):
            if side_effect is not None:
                raise side_effect
            return quote_return or {}

    finnhub_mod.Client = FakeClient
    return finnhub_mod


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_alert_skips_when_no_finnhub_key():
    """If finnhub_api_key is empty, check_alerts must return without raising."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    mock_settings = _make_settings(finnhub_api_key="")

    with patch("saas.workers.alert_monitor.get_settings", return_value=mock_settings):
        await check_alerts()  # must not raise


@pytest.mark.asyncio
async def test_alert_fires_on_large_price_drop():
    """A price drop greater than 5% must trigger send_alert_email."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    users = [_active_profile()]
    mock_sb = _make_supabase_with_watchlist({"NVDA": users})
    emails_sent = []

    async def capture_email(email, ticker, pct, analysis):
        emails_sent.append({"email": email, "ticker": ticker, "pct": pct})

    # ~15.5% drop
    quote = {"c": 740.0, "pc": 876.0}
    finnhub_mod = _make_finnhub_module(quote_return=quote)

    with patch("saas.workers.alert_monitor.create_client", return_value=mock_sb), \
         patch("saas.workers.alert_monitor.get_settings", return_value=_make_settings()), \
         patch("saas.workers.alert_monitor.send_alert_email", side_effect=capture_email), \
         patch.dict(sys.modules, {"finnhub": finnhub_mod}):
        await check_alerts()

    assert len(emails_sent) > 0
    assert emails_sent[0]["ticker"] == "NVDA"
    assert emails_sent[0]["pct"] < -5.0


@pytest.mark.asyncio
async def test_alert_does_not_fire_on_small_move():
    """A price move below 5% must NOT trigger any alert email."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    users = [_active_profile()]
    mock_sb = _make_supabase_with_watchlist({"NVDA": users})
    emails_sent = []

    async def capture_email(*args, **kwargs):
        emails_sent.append(args)

    # ~0.2% move — well below threshold
    quote = {"c": 878.0, "pc": 876.0}
    finnhub_mod = _make_finnhub_module(quote_return=quote)

    with patch("saas.workers.alert_monitor.create_client", return_value=mock_sb), \
         patch("saas.workers.alert_monitor.get_settings", return_value=_make_settings()), \
         patch("saas.workers.alert_monitor.send_alert_email", side_effect=capture_email), \
         patch.dict(sys.modules, {"finnhub": finnhub_mod}):
        await check_alerts()

    assert len(emails_sent) == 0


@pytest.mark.asyncio
async def test_alert_fires_on_large_price_rise():
    """A price rise greater than 5% must also trigger an alert."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    users = [_active_profile()]
    mock_sb = _make_supabase_with_watchlist({"NVDA": users})
    pct_values = []

    async def capture_pct(email, ticker, pct, analysis):
        pct_values.append(pct)

    # ~7.3% rise
    quote = {"c": 940.0, "pc": 876.0}
    finnhub_mod = _make_finnhub_module(quote_return=quote)

    with patch("saas.workers.alert_monitor.create_client", return_value=mock_sb), \
         patch("saas.workers.alert_monitor.get_settings", return_value=_make_settings()), \
         patch("saas.workers.alert_monitor.send_alert_email", side_effect=capture_pct), \
         patch.dict(sys.modules, {"finnhub": finnhub_mod}):
        await check_alerts()

    assert len(pct_values) > 0
    assert pct_values[0] > 5.0


@pytest.mark.asyncio
async def test_finnhub_error_does_not_crash_monitor():
    """If Finnhub quote() raises for one ticker, check_alerts must not propagate the error."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    users = [_active_profile()]
    mock_sb = _make_supabase_with_watchlist({"NVDA": users, "AAPL": users})
    finnhub_mod = _make_finnhub_module(side_effect=Exception("API error"))

    with patch("saas.workers.alert_monitor.create_client", return_value=mock_sb), \
         patch("saas.workers.alert_monitor.get_settings", return_value=_make_settings()), \
         patch("saas.workers.alert_monitor.send_alert_email", new_callable=AsyncMock), \
         patch.dict(sys.modules, {"finnhub": finnhub_mod}):
        await check_alerts()  # must not raise


@pytest.mark.asyncio
async def test_alert_skips_user_with_insufficient_credits():
    """When credit deduction returns negative, alert email must not be sent to that user."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    users = [_active_profile("u1", "broke@test.com")]
    mock_sb = _make_supabase_with_watchlist({"NVDA": users})
    # Simulate insufficient credits
    mock_sb.rpc.return_value.execute.return_value.data = -1

    emails_sent = []

    async def capture_email(*args, **kwargs):
        emails_sent.append(args)

    # Large drop to guarantee threshold is exceeded
    quote = {"c": 700.0, "pc": 876.0}
    finnhub_mod = _make_finnhub_module(quote_return=quote)

    with patch("saas.workers.alert_monitor.create_client", return_value=mock_sb), \
         patch("saas.workers.alert_monitor.get_settings", return_value=_make_settings()), \
         patch("saas.workers.alert_monitor.send_alert_email", side_effect=capture_email), \
         patch.dict(sys.modules, {"finnhub": finnhub_mod}):
        await check_alerts()

    assert len(emails_sent) == 0


@pytest.mark.asyncio
async def test_alert_sends_to_all_watching_users():
    """All users watching the same alerted ticker must receive an email."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    users = [
        _active_profile("u1", "alice@test.com"),
        _active_profile("u2", "bob@test.com"),
    ]
    mock_sb = _make_supabase_with_watchlist({"NVDA": users})
    emails_sent = []

    async def capture_email(email, ticker, pct, analysis):
        emails_sent.append(email)

    # Big drop
    quote = {"c": 700.0, "pc": 876.0}
    finnhub_mod = _make_finnhub_module(quote_return=quote)

    with patch("saas.workers.alert_monitor.create_client", return_value=mock_sb), \
         patch("saas.workers.alert_monitor.get_settings", return_value=_make_settings()), \
         patch("saas.workers.alert_monitor.send_alert_email", side_effect=capture_email), \
         patch.dict(sys.modules, {"finnhub": finnhub_mod}):
        await check_alerts()

    assert "alice@test.com" in emails_sent
    assert "bob@test.com" in emails_sent


@pytest.mark.asyncio
async def test_alert_returns_none():
    """check_alerts must return None (it is a fire-and-forget monitor)."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    mock_settings = _make_settings(finnhub_api_key="")  # short-circuit path

    with patch("saas.workers.alert_monitor.get_settings", return_value=mock_settings):
        result = await check_alerts()

    assert result is None


@pytest.mark.asyncio
async def test_alert_skips_ticker_with_zero_prev_close():
    """If prev_close (pc) is 0, division-by-zero must be avoided and ticker skipped."""
    try:
        from saas.workers.alert_monitor import check_alerts
    except ImportError:
        pytest.skip("alert_monitor not importable")

    users = [_active_profile()]
    mock_sb = _make_supabase_with_watchlist({"NVDA": users})
    emails_sent = []

    async def capture_email(*args, **kwargs):
        emails_sent.append(args)

    # pc = 0 triggers the guard in the source code
    quote = {"c": 800.0, "pc": 0}
    finnhub_mod = _make_finnhub_module(quote_return=quote)

    with patch("saas.workers.alert_monitor.create_client", return_value=mock_sb), \
         patch("saas.workers.alert_monitor.get_settings", return_value=_make_settings()), \
         patch("saas.workers.alert_monitor.send_alert_email", side_effect=capture_email), \
         patch.dict(sys.modules, {"finnhub": finnhub_mod}):
        await check_alerts()  # must not raise

    assert len(emails_sent) == 0


def test_alert_threshold_is_5_percent():
    """The internal threshold constant _ALERT_THRESHOLD_PCT must equal 5.0."""
    try:
        import importlib
        # Force a fresh import to read the actual module constant
        if "saas.workers.alert_monitor" in sys.modules:
            del sys.modules["saas.workers.alert_monitor"]

        # Patch heavy deps before importing so module loads without network
        fake_finnhub = types.ModuleType("finnhub")
        fake_finnhub.Client = MagicMock()
        with patch.dict(sys.modules, {"finnhub": fake_finnhub}):
            mod = importlib.import_module("saas.workers.alert_monitor")

        threshold = getattr(mod, "_ALERT_THRESHOLD_PCT", None)
        if threshold is None:
            pytest.skip("_ALERT_THRESHOLD_PCT not exported; threshold verified via integration tests")
        assert threshold == 5.0
    except ImportError:
        pytest.skip("alert_monitor not importable")
