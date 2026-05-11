"""P2: Analysis worker concurrency — parallel execution, error handling, result isolation.

Note: analysis_worker.run_analysis_task is a plain async function that returns
{"final_state": ..., "signal": ...}.  There is no built-in task-registry or
semaphore in the module; these tests validate the function's contract under
concurrent load using asyncio.gather.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

try:
    from saas.workers import analysis_worker
    from saas.workers.analysis_worker import run_analysis_task
    WORKER_AVAILABLE = True
except ImportError:
    WORKER_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not WORKER_AVAILABLE,
    reason="analysis_worker not importable (supabase missing or saas package absent)",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_supabase_mock():
    """Return a MagicMock that satisfies all Supabase calls made by run_analysis_task."""
    mock_sb = MagicMock()
    # portfolio_holdings fetch (returns empty — no holdings to pre-load)
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
    # verdicts insert
    mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{}]
    # analyses count for first-analysis lifecycle event
    count_result = MagicMock()
    count_result.count = 0
    mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = count_result
    return mock_sb


def _make_settings_mock(ticker="NVDA"):
    """Return a MagicMock settings object with provider defaults."""
    settings = MagicMock()
    settings.supabase_url = "https://fake.supabase.co"
    settings.supabase_service_role_key = "fake-key"
    settings.analyst_provider = "openai"
    settings.analyst_model = "gpt-4o-mini"
    settings.synthesis_provider = "openai"
    settings.synthesis_model = "gpt-4o-mini"
    return settings


def _make_analysis_state(ticker: str, decision: str = "BUY — strong thesis"):
    """Return a minimal AnalysisState-like object accepted by run_analysis_task."""
    from tradingagents.pipeline.state import AnalysisState
    return AnalysisState(
        ticker=ticker,
        trade_date="2026-01-12",
        final_decision=decision,
    )


# ---------------------------------------------------------------------------
# Basic contract: single successful call
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_analysis_task_returns_correct_keys():
    """run_analysis_task must return a dict with 'final_state' and 'signal'."""
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()

    async def mock_run_analysis(**kwargs):
        return _make_analysis_state("NVDA", "BUY — conviction")

    mock_checkpoint = MagicMock()

    with patch("saas.workers.analysis_worker.run_analysis", new=mock_run_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        result = await run_analysis_task(
            user_id="user-123",
            ticker="NVDA",
            trade_date="2026-01-12",
        )

    assert "final_state" in result, "Result must contain 'final_state'"
    assert "signal" in result, "Result must contain 'signal'"
    assert result["signal"] == "BUY"


@pytest.mark.asyncio
async def test_run_analysis_task_final_state_contains_ticker():
    """final_state['company_of_interest'] must match the requested ticker."""
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    async def mock_run_analysis(**kwargs):
        return _make_analysis_state("AAPL", "HOLD — wait for earnings")

    with patch("saas.workers.analysis_worker.run_analysis", new=mock_run_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        result = await run_analysis_task(
            user_id="user-123",
            ticker="AAPL",
            trade_date="2026-01-12",
        )

    assert result["final_state"]["company_of_interest"] == "AAPL"


# ---------------------------------------------------------------------------
# Signal extraction
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("decision,expected_signal", [
    ("BUY — high conviction", "BUY"),
    ("SELL — bear thesis confirmed", "SELL"),
    ("HOLD — wait for next quarter", "HOLD"),
    ("", "HOLD"),  # empty decision falls back to HOLD
])
@pytest.mark.asyncio
async def test_signal_extracted_from_decision(decision, expected_signal):
    """_extract_signal must correctly map decision text to BUY/SELL/HOLD."""
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    async def mock_run_analysis(**kwargs):
        return _make_analysis_state("NVDA", decision)

    with patch("saas.workers.analysis_worker.run_analysis", new=mock_run_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        result = await run_analysis_task(
            user_id="user-123",
            ticker="NVDA",
            trade_date="2026-01-12",
        )

    assert result["signal"] == expected_signal


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_exception_from_run_analysis_propagates():
    """If run_analysis raises, run_analysis_task must propagate the exception
    rather than swallowing it and returning a partial result."""
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    async def failing_analysis(**kwargs):
        raise ValueError("LLM API timeout")

    with patch("saas.workers.analysis_worker.run_analysis", new=failing_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint):
        with pytest.raises(ValueError, match="LLM API timeout"):
            await run_analysis_task(
                user_id="user-123",
                ticker="NVDA",
                trade_date="2026-01-12",
            )


# ---------------------------------------------------------------------------
# Concurrency: separate results, no state bleed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_concurrent_tasks_return_separate_results():
    """Two simultaneous analyses must not share or overwrite each other's result.

    Uses asyncio.gather to run them truly concurrently within the event loop.
    """
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    async def slow_analysis(**kwargs):
        ticker = kwargs.get("ticker", "UNKNOWN")
        await asyncio.sleep(0.05)
        return _make_analysis_state(ticker, f"BUY — {ticker} thesis")

    shared_patches = dict(
        run_analysis=slow_analysis,
        create_client=lambda *a, **kw: mock_sb,
        get_settings=lambda: settings,
        get_checkpoint=lambda **kw: mock_checkpoint,
    )

    with patch("saas.workers.analysis_worker.run_analysis", new=slow_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        result_nvda, result_aapl = await asyncio.gather(
            run_analysis_task("user-1", "NVDA", "2026-01-12"),
            run_analysis_task("user-2", "AAPL", "2026-01-12"),
        )

    assert result_nvda["final_state"]["company_of_interest"] == "NVDA"
    assert result_aapl["final_state"]["company_of_interest"] == "AAPL"
    assert result_nvda["signal"] == "BUY"
    assert result_aapl["signal"] == "BUY"
    # Ensure the two result dicts are distinct objects
    assert result_nvda is not result_aapl


@pytest.mark.asyncio
async def test_concurrent_tasks_same_user_different_tickers():
    """One user running two analyses concurrently must get two independent results."""
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    call_order = []

    async def tracking_analysis(**kwargs):
        ticker = kwargs.get("ticker", "X")
        call_order.append(f"start-{ticker}")
        await asyncio.sleep(0.02)
        call_order.append(f"end-{ticker}")
        return _make_analysis_state(ticker, "SELL — overvalued")

    with patch("saas.workers.analysis_worker.run_analysis", new=tracking_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        results = await asyncio.gather(
            run_analysis_task("user-1", "NVDA", "2026-01-12"),
            run_analysis_task("user-1", "MSFT", "2026-01-12"),
        )

    tickers = {r["final_state"]["company_of_interest"] for r in results}
    assert tickers == {"NVDA", "MSFT"}, f"Expected both tickers, got {tickers}"
    signals = {r["signal"] for r in results}
    assert signals == {"SELL"}
    # Both analyses must have started before either finished (true concurrency)
    assert call_order.index("start-NVDA") < call_order.index("end-MSFT") or \
           call_order.index("start-MSFT") < call_order.index("end-NVDA"), \
           "Tasks did not execute concurrently"


@pytest.mark.asyncio
async def test_concurrent_tasks_one_fails_other_succeeds():
    """When one concurrent analysis raises, the other must still complete.

    Uses asyncio.gather(return_exceptions=True) to collect both outcomes.
    """
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    async def mixed_analysis(**kwargs):
        ticker = kwargs.get("ticker", "X")
        await asyncio.sleep(0.01)
        if ticker == "FAIL":
            raise RuntimeError("Simulated API failure")
        return _make_analysis_state(ticker, "HOLD — neutral")

    with patch("saas.workers.analysis_worker.run_analysis", new=mixed_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        results = await asyncio.gather(
            run_analysis_task("user-1", "NVDA", "2026-01-12"),
            run_analysis_task("user-2", "FAIL", "2026-01-12"),
            return_exceptions=True,
        )

    nvda_result, fail_result = results
    assert isinstance(fail_result, RuntimeError), \
        f"Expected RuntimeError for failing task, got {type(fail_result)}"
    assert nvda_result["signal"] == "HOLD", \
        f"Successful task must still return a result, got {nvda_result}"


# ---------------------------------------------------------------------------
# Portfolio context isolation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_portfolio_context_fetched_per_user():
    """Each call must fetch portfolio holdings scoped to its own user_id."""
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    fetch_calls = []

    def make_user_sb(user_id):
        mock_sb = MagicMock()
        # Track which user_id was passed to the eq() filter
        def track_eq(col, val):
            if col == "user_id":
                fetch_calls.append(val)
            return mock_sb.table.return_value.select.return_value.eq.return_value
        mock_sb.table.return_value.select.return_value.eq.side_effect = track_eq
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        mock_sb.table.return_value.insert.return_value.execute.return_value.data = [{}]
        count_result = MagicMock()
        count_result.count = 0
        mock_sb.table.return_value.select.return_value.eq.return_value.execute.return_value = count_result
        return mock_sb

    async def mock_run_analysis(**kwargs):
        ticker = kwargs.get("ticker", "X")
        return _make_analysis_state(ticker, "BUY")

    # Run two tasks; create_client is called once per task
    sb_a = make_user_sb("user-A")
    sb_b = make_user_sb("user-B")
    clients = iter([sb_a, sb_b])

    with patch("saas.workers.analysis_worker.run_analysis", new=mock_run_analysis), \
         patch("saas.workers.analysis_worker.create_client", side_effect=lambda *a, **kw: next(clients)), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        await asyncio.gather(
            run_analysis_task("user-A", "NVDA", "2026-01-12"),
            run_analysis_task("user-B", "AAPL", "2026-01-12"),
        )

    # Both user IDs must have been used in separate eq() calls
    assert "user-A" in fetch_calls, "Portfolio fetch for user-A not found"
    assert "user-B" in fetch_calls, "Portfolio fetch for user-B not found"


# ---------------------------------------------------------------------------
# config overrides
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_config_task_id_override_passed_to_checkpoint():
    """When config contains 'task_id', get_checkpoint must receive that task_id."""
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()

    checkpoint_kwargs = {}

    def capture_checkpoint(**kwargs):
        checkpoint_kwargs.update(kwargs)
        return MagicMock()

    async def mock_run_analysis(**kwargs):
        return _make_analysis_state("NVDA", "BUY")

    with patch("saas.workers.analysis_worker.run_analysis", new=mock_run_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", side_effect=capture_checkpoint), \
         patch("saas.workers.analysis_worker._log_verdict"):
        await run_analysis_task(
            user_id="user-123",
            ticker="NVDA",
            trade_date="2026-01-12",
            config={"task_id": "my-custom-task-id"},
        )

    assert checkpoint_kwargs.get("task_id") == "my-custom-task-id", \
        f"Expected task_id='my-custom-task-id', got {checkpoint_kwargs.get('task_id')}"


@pytest.mark.asyncio
async def test_portfolio_context_not_fetched_when_provided():
    """When portfolio_context is passed in, _fetch_portfolio_context must NOT
    be called — the pre-fetched dict must be used as-is."""
    mock_sb = _make_supabase_mock()
    settings = _make_settings_mock()
    mock_checkpoint = MagicMock()

    received_portfolio = {}

    async def capturing_analysis(**kwargs):
        received_portfolio.update(kwargs.get("portfolio_context", {}))
        return _make_analysis_state("NVDA", "BUY")

    pre_fetched = {"NVDA": {"shares": 100, "avg_cost_usd": 500.0}}

    with patch("saas.workers.analysis_worker.run_analysis", new=capturing_analysis), \
         patch("saas.workers.analysis_worker.create_client", return_value=mock_sb), \
         patch("saas.workers.analysis_worker.get_settings", return_value=settings), \
         patch("saas.workers.analysis_worker.get_checkpoint", return_value=mock_checkpoint), \
         patch("saas.workers.analysis_worker._fetch_portfolio_context") as mock_fetch, \
         patch("saas.workers.analysis_worker._log_verdict"):
        await run_analysis_task(
            user_id="user-123",
            ticker="NVDA",
            trade_date="2026-01-12",
            portfolio_context=pre_fetched,
        )

    mock_fetch.assert_not_called()
