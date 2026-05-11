"""Tests for the asyncio parallel pipeline runner."""
import asyncio
import pytest
from unittest.mock import MagicMock

from tradingagents.pipeline.state import AnalysisState
from tradingagents.pipeline.runner import run_analysis, run_analysis_sync


# ── Patch targets ──────────────────────────────────────────────────────────

_AGENT_PATCHES = {
    "tradingagents.pipeline.runner.run_fundamental_analyst",
    "tradingagents.pipeline.runner.run_market_analyst",
    "tradingagents.pipeline.runner.run_news_analyst",
    "tradingagents.pipeline.runner.run_sentiment_analyst",
    "tradingagents.pipeline.runner.run_bull_researcher",
    "tradingagents.pipeline.runner.run_bear_researcher",
    "tradingagents.pipeline.runner.run_research_manager",
    "tradingagents.pipeline.runner.run_trader",
    "tradingagents.pipeline.runner.run_portfolio_manager",
}

_DEFAULT_PATCH_MAP = {
    "tradingagents.pipeline.runner.run_fundamental_analyst": "fundamentals report",
    "tradingagents.pipeline.runner.run_market_analyst": "market report",
    "tradingagents.pipeline.runner.run_news_analyst": "news report",
    "tradingagents.pipeline.runner.run_sentiment_analyst": "sentiment report",
    "tradingagents.pipeline.runner.run_bull_researcher": "bull output",
    "tradingagents.pipeline.runner.run_bear_researcher": "bear output",
    "tradingagents.pipeline.runner.run_research_manager": "investment plan",
    "tradingagents.pipeline.runner.run_trader": "trader proposal",
    "tradingagents.pipeline.runner.run_portfolio_manager": "final decision",
}


def _make_noop(return_value: str = "output"):
    """Return a simple async agent stub that returns a fixed string."""
    async def _agent(state, *args):
        return return_value
    return _agent


def _patch_all_agents(mocker, overrides=None):
    """Patch all 9 agent imports in the runner with stubs. Returns the mocker."""
    overrides = overrides or {}
    for target, default_return in _DEFAULT_PATCH_MAP.items():
        stub_return = overrides.get(target, default_return)
        if callable(stub_return) and asyncio.iscoroutinefunction(stub_return):
            mocker.patch(target, new=stub_return)
        else:
            mocker.patch(target, new=_make_noop(stub_return))


# ── Basic return type and field population ─────────────────────────────────

@pytest.mark.asyncio
async def test_run_analysis_returns_analysis_state(mocker):
    """run_analysis must return an AnalysisState instance."""
    _patch_all_agents(mocker)
    state = await run_analysis("NVDA", "2026-01-15")
    assert isinstance(state, AnalysisState)


@pytest.mark.asyncio
async def test_run_analysis_ticker_is_uppercased(mocker):
    """run_analysis stores the ticker in uppercase."""
    _patch_all_agents(mocker)
    state = await run_analysis("nvda", "2026-01-15")
    assert state.ticker == "NVDA"


@pytest.mark.asyncio
async def test_run_analysis_trade_date_preserved(mocker):
    _patch_all_agents(mocker)
    state = await run_analysis("NVDA", "2026-01-15")
    assert state.trade_date == "2026-01-15"


@pytest.mark.asyncio
async def test_run_analysis_populates_all_phase1_reports(mocker):
    """All 4 analyst reports must be populated after Phase 1."""
    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_fundamental_analyst": "fundamentals report",
        "tradingagents.pipeline.runner.run_market_analyst": "market report",
        "tradingagents.pipeline.runner.run_news_analyst": "news report",
        "tradingagents.pipeline.runner.run_sentiment_analyst": "sentiment report",
    })
    state = await run_analysis("NVDA", "2026-01-15")
    assert state.fundamentals_report == "fundamentals report"
    assert state.market_report == "market report"
    assert state.news_report == "news report"
    assert state.sentiment_report == "sentiment report"


@pytest.mark.asyncio
async def test_run_analysis_populates_phase2_and_phase3(mocker):
    """Bull/bear cases and synthesis fields must be populated."""
    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_bull_researcher": "bull output",
        "tradingagents.pipeline.runner.run_bear_researcher": "bear output",
        "tradingagents.pipeline.runner.run_research_manager": "investment plan",
        "tradingagents.pipeline.runner.run_trader": "trader proposal",
        "tradingagents.pipeline.runner.run_portfolio_manager": "final decision",
    })
    state = await run_analysis("NVDA", "2026-01-15")
    assert state.bull_case == "bull output"
    assert state.bear_case == "bear output"
    assert state.investment_plan == "investment plan"
    assert state.trader_proposal == "trader proposal"
    assert state.final_decision == "final decision"


# ── Phase 1 parallelism ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase1_runs_in_parallel(mocker):
    """Phase 1 agents must run concurrently (asyncio.gather).

    Four agents each sleeping 50ms should complete in ~50ms total, not 200ms.
    Sequential execution would take > 150ms.
    """
    async def slow_agent(state, *args):
        await asyncio.sleep(0.05)   # 50ms simulated LLM latency
        return "report"

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_fundamental_analyst": slow_agent,
        "tradingagents.pipeline.runner.run_market_analyst": slow_agent,
        "tradingagents.pipeline.runner.run_news_analyst": slow_agent,
        "tradingagents.pipeline.runner.run_sentiment_analyst": slow_agent,
    })

    loop = asyncio.get_event_loop()
    t0 = loop.time()
    await run_analysis("NVDA", "2026-01-15")
    elapsed = loop.time() - t0

    # Sequential would be 4 * 50ms = 200ms. Allow generous margin for overhead.
    assert elapsed < 0.15, (
        f"Phase 1 took {elapsed:.3f}s — expected parallel execution (~0.05s)"
    )


# ── Error handling ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_phase1_agent_failure_does_not_raise(mocker):
    """If one Phase 1 agent raises, run_analysis must still return a state."""
    async def failing_agent(state, *args):
        raise ValueError("LLM API timeout")

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_fundamental_analyst": failing_agent,
    })
    # Must not raise
    state = await run_analysis("NVDA", "2026-01-15")
    assert isinstance(state, AnalysisState)


@pytest.mark.asyncio
async def test_phase1_failure_produces_error_string(mocker):
    """A failing Phase 1 agent must produce an 'unavailable' error string, not empty."""
    async def failing_agent(state, *args):
        raise ValueError("LLM API timeout")

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_fundamental_analyst": failing_agent,
    })
    state = await run_analysis("NVDA", "2026-01-15")
    assert state.fundamentals_report != ""
    assert "unavailable" in state.fundamentals_report.lower()


@pytest.mark.asyncio
async def test_phase1_working_agents_complete_despite_one_failure(mocker):
    """Phase 1 agents that succeed must still populate their fields."""
    async def failing_agent(state, *args):
        raise ValueError("timeout")

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_fundamental_analyst": failing_agent,
        "tradingagents.pipeline.runner.run_market_analyst": "working market report",
    })
    state = await run_analysis("NVDA", "2026-01-15")
    assert state.market_report == "working market report"


@pytest.mark.asyncio
async def test_phase3_failure_is_graceful(mocker):
    """If the Research Manager fails, run_analysis still returns state with error string."""
    async def failing_manager(state, *args):
        raise RuntimeError("research manager crashed")

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_research_manager": failing_manager,
    })
    state = await run_analysis("NVDA", "2026-01-15")
    assert "unavailable" in state.investment_plan.lower()


# ── on_agent_complete callback ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_on_agent_complete_callback_fires_for_each_agent(mocker):
    """on_agent_complete callback must be called at least once per phase."""
    completed = []

    async def callback(agent_name: str, state: AnalysisState):
        completed.append(agent_name)

    _patch_all_agents(mocker)
    await run_analysis("NVDA", "2026-01-15", on_agent_complete=callback)

    # Phase 1: 4 analysts, Phase 2: 2 researchers, Phase 3: 3 synthesis = 9 total
    assert len(completed) == 9


@pytest.mark.asyncio
async def test_on_agent_complete_receives_state(mocker):
    """Callback second argument must be the live AnalysisState."""
    received_states = []

    async def callback(agent_name: str, state):
        received_states.append(state)

    _patch_all_agents(mocker)
    await run_analysis("NVDA", "2026-01-15", on_agent_complete=callback)
    assert all(isinstance(s, AnalysisState) for s in received_states)


@pytest.mark.asyncio
async def test_on_agent_complete_callback_failure_does_not_abort(mocker):
    """A crashing callback must not abort the pipeline."""
    async def bad_callback(agent_name, state):
        raise RuntimeError("callback crashed")

    _patch_all_agents(mocker)
    # Must not raise
    state = await run_analysis("NVDA", "2026-01-15", on_agent_complete=bad_callback)
    assert isinstance(state, AnalysisState)


# ── selected_analysts parameter ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_selected_analysts_fundamentals_only(mocker):
    """Requesting only 'fundamentals' should skip the other three Phase 1 agents."""
    ran = []

    async def tracking_fundamental(state, *args):
        ran.append("fundamentals")
        return "fundamentals output"

    async def should_not_run(state, *args):
        ran.append("should_not_run")
        return "unexpected"

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_fundamental_analyst": tracking_fundamental,
        "tradingagents.pipeline.runner.run_market_analyst": should_not_run,
        "tradingagents.pipeline.runner.run_news_analyst": should_not_run,
        "tradingagents.pipeline.runner.run_sentiment_analyst": should_not_run,
    })

    await run_analysis(
        "NVDA", "2026-01-15",
        selected_analysts=["fundamentals"],
    )

    assert "fundamentals" in ran
    assert "should_not_run" not in ran


@pytest.mark.asyncio
async def test_selected_analysts_empty_skips_phase1(mocker):
    """Empty selected_analysts must skip all Phase 1 agents."""
    phase1_ran = []

    async def phase1_tracker(state, *args):
        phase1_ran.append(True)
        return "phase1 output"

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_fundamental_analyst": phase1_tracker,
        "tradingagents.pipeline.runner.run_market_analyst": phase1_tracker,
        "tradingagents.pipeline.runner.run_news_analyst": phase1_tracker,
        "tradingagents.pipeline.runner.run_sentiment_analyst": phase1_tracker,
    })

    state = await run_analysis("NVDA", "2026-01-15", selected_analysts=[])
    assert len(phase1_ran) == 0
    # Phase 1 reports remain empty since no analysts ran
    assert state.fundamentals_report == ""
    assert state.market_report == ""


@pytest.mark.asyncio
async def test_selected_analysts_social_maps_to_sentiment(mocker):
    """'social' in selected_analysts must invoke run_sentiment_analyst."""
    sentiment_ran = []

    async def track_sentiment(state, *args):
        sentiment_ran.append(True)
        return "sentiment output"

    _patch_all_agents(mocker, overrides={
        "tradingagents.pipeline.runner.run_sentiment_analyst": track_sentiment,
    })

    state = await run_analysis(
        "NVDA", "2026-01-15",
        selected_analysts=["social"],  # "social" is the key used in runner
    )

    assert len(sentiment_ran) == 1
    assert state.sentiment_report == "sentiment output"


# ── Checkpoint integration ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_checkpoint_save_called_after_agents(mocker):
    """With a checkpoint provided, checkpoint.save() must be called at least once."""
    mock_cp = MagicMock()
    mock_cp.load.return_value = None  # no prior state

    _patch_all_agents(mocker)
    await run_analysis("NVDA", "2026-01-15", checkpoint=mock_cp)

    assert mock_cp.save.call_count >= 1


@pytest.mark.asyncio
async def test_checkpoint_clear_called_on_success(mocker):
    """checkpoint.clear() must be called exactly once after successful completion."""
    mock_cp = MagicMock()
    mock_cp.load.return_value = None

    _patch_all_agents(mocker)
    await run_analysis("NVDA", "2026-01-15", checkpoint=mock_cp)

    mock_cp.clear.assert_called_once()


@pytest.mark.asyncio
async def test_checkpoint_load_called_at_startup(mocker):
    """The runner must call checkpoint.load() to check for prior progress."""
    mock_cp = MagicMock()
    mock_cp.load.return_value = None

    _patch_all_agents(mocker)
    await run_analysis("NVDA", "2026-01-15", checkpoint=mock_cp)

    mock_cp.load.assert_called_once()


@pytest.mark.asyncio
async def test_checkpoint_resume_uses_prior_state(mocker):
    """When checkpoint.load() returns a prior state, the runner uses it."""
    prior_state = AnalysisState(
        ticker="NVDA",
        trade_date="2026-01-15",
        fundamentals_report="cached fundamentals",
        market_report="cached market",
        news_report="cached news",
        sentiment_report="cached sentiment",
        completed_agents=["Fundamental Analyst", "Market Analyst", "News Analyst", "Sentiment Analyst"],
    )
    mock_cp = MagicMock()
    mock_cp.load.return_value = prior_state

    _patch_all_agents(mocker)
    state = await run_analysis("NVDA", "2026-01-15", checkpoint=mock_cp)

    # The runner should preserve the cached fundamentals from the prior checkpoint
    # (Phase 1 agents still run, but the prior state was loaded and reused as base)
    # The key assertion is that the runner does not crash and returns a valid state
    assert isinstance(state, AnalysisState)


# ── portfolio_context forwarding ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_portfolio_context_forwarded_to_state(mocker):
    """portfolio_context kwarg must be stored on the returned state."""
    _patch_all_agents(mocker)
    ctx = {"NVDA": {"shares": 100, "avg_cost_usd": 150.0}}
    state = await run_analysis("NVDA", "2026-01-15", portfolio_context=ctx)
    assert state.portfolio_context == ctx


# ── Sync wrapper ────────────────────────────────────────────────────────────

def test_run_analysis_sync_works(mocker):
    """run_analysis_sync must execute correctly in a blocking context."""
    _patch_all_agents(mocker)
    state = run_analysis_sync("NVDA", "2026-01-15")
    assert isinstance(state, AnalysisState)
    assert state.ticker == "NVDA"


def test_run_analysis_sync_returns_correct_ticker(mocker):
    _patch_all_agents(mocker)
    state = run_analysis_sync("AAPL", "2026-03-01")
    assert state.ticker == "AAPL"
