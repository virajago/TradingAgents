"""Tests for AnalysisState dataclass."""
import pytest
from tradingagents.pipeline.state import AnalysisState


def test_initial_state_has_correct_ticker_and_date():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    assert state.ticker == "NVDA"
    assert state.trade_date == "2026-01-15"


def test_initial_state_reports_are_empty():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    assert state.fundamentals_report == ""
    assert state.market_report == ""
    assert state.sentiment_report == ""
    assert state.news_report == ""
    assert state.bull_case == ""
    assert state.bear_case == ""
    assert state.investment_plan == ""
    assert state.trader_proposal == ""
    assert state.final_decision == ""


def test_initial_state_tracking_fields_are_empty():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    assert state.completed_agents == []
    assert state.agent_summaries == {}


def test_initial_portfolio_context_is_empty_dict():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    assert state.portfolio_context == {}


def test_mark_complete_appends_agent():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    state.mark_complete("Fundamental Analyst", "Q1 guidance raised")
    assert "Fundamental Analyst" in state.completed_agents
    assert state.agent_summaries["Fundamental Analyst"] == "Q1 guidance raised"


def test_mark_complete_multiple_agents():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    state.mark_complete("Fundamental Analyst", "fundamentals done")
    state.mark_complete("News Analyst", "news done")
    assert len(state.completed_agents) == 2
    assert "Fundamental Analyst" in state.completed_agents
    assert "News Analyst" in state.completed_agents


def test_mark_complete_truncates_long_summary():
    """Summaries longer than 200 chars are stored truncated to 200 chars."""
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    long_summary = "x" * 300
    state.mark_complete("News Analyst", long_summary)
    assert len(state.agent_summaries["News Analyst"]) == 200


def test_mark_complete_preserves_short_summary():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    short = "Short summary"
    state.mark_complete("Trader", short)
    assert state.agent_summaries["Trader"] == short


def test_mark_complete_empty_summary_not_stored():
    """An empty summary must not create an entry in agent_summaries."""
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    state.mark_complete("Bull Researcher")  # no summary
    assert "Bull Researcher" in state.completed_agents
    assert "Bull Researcher" not in state.agent_summaries


def test_portfolio_context_str_empty_when_no_holdings():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    assert state.portfolio_context_str() == ""


def test_portfolio_context_str_empty_when_empty_dict():
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15", portfolio_context={})
    assert state.portfolio_context_str() == ""


def test_portfolio_context_str_when_ticker_held():
    state = AnalysisState(
        ticker="NVDA",
        trade_date="2026-01-15",
        portfolio_context={"NVDA": {"shares": 200, "avg_cost_usd": 118.0}},
    )
    ctx = state.portfolio_context_str()
    assert "200" in ctx
    assert "118" in ctx
    assert "NVDA" in ctx


def test_portfolio_context_str_includes_total_invested():
    state = AnalysisState(
        ticker="NVDA",
        trade_date="2026-01-15",
        portfolio_context={"NVDA": {"shares": 100, "avg_cost_usd": 200.0}},
    )
    ctx = state.portfolio_context_str()
    # 100 shares * $200 = $20,000 total
    assert "20,000" in ctx or "20000" in ctx


def test_portfolio_context_str_empty_when_different_ticker():
    """Context string is empty when user doesn't hold the analyzed ticker."""
    state = AnalysisState(
        ticker="AAPL",
        trade_date="2026-01-15",
        portfolio_context={"NVDA": {"shares": 200, "avg_cost_usd": 118.0}},
    )
    assert state.portfolio_context_str() == ""


def test_portfolio_context_str_case_insensitive_lookup():
    """portfolio_context lookup must work regardless of ticker case in context."""
    state = AnalysisState(
        ticker="nvda",  # lowercase ticker on state
        trade_date="2026-01-15",
        portfolio_context={"NVDA": {"shares": 50, "avg_cost_usd": 100.0}},
    )
    # The method does ticker.upper() before lookup, so it should still find the holding
    ctx = state.portfolio_context_str()
    assert "50" in ctx


def test_debate_history_field_exists():
    """debate_history is a separate field from bull_case/bear_case."""
    state = AnalysisState(ticker="NVDA", trade_date="2026-01-15")
    assert state.debate_history == ""
    state.debate_history = "some debate"
    assert state.debate_history == "some debate"
