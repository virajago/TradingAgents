"""Main analysis pipeline — asyncio parallel execution, no LangGraph.

Phase 1 (parallel):   Fundamental, Market, News, Sentiment analysts
Phase 2 (parallel):   Bull Researcher, Bear Researcher
Phase 3 (sequential): Research Manager -> Trader -> Portfolio Manager

Total time: ~90-120 seconds with fast models for Phase 1.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, Optional

from tradingagents.pipeline.state import AnalysisState
from tradingagents.pipeline.agents import (
    run_fundamental_analyst,
    run_market_analyst,
    run_news_analyst,
    run_sentiment_analyst,
    run_bull_researcher,
    run_bear_researcher,
    run_research_manager,
    run_trader,
    run_portfolio_manager,
)

logger = logging.getLogger(__name__)

AgentCallback = Callable[[str, AnalysisState], Awaitable[None]]


async def run_analysis(
    ticker: str,
    trade_date: str,
    *,
    # Model config — defaults match the two-tier cost strategy
    analyst_provider: str = None,   # defaults to ANALYST_PROVIDER env var or gemini-3-flash-preview
    analyst_model: str = None,      # defaults to ANALYST_MODEL env var
    synthesis_provider: str = None, # defaults to SYNTHESIS_PROVIDER env var
    synthesis_model: str = None,    # defaults to SYNTHESIS_MODEL env var
    portfolio_context: Optional[dict] = None,
    on_agent_complete: Optional[AgentCallback] = None,
    selected_analysts: tuple | list = ("market", "social", "news", "fundamentals"),
    checkpoint=None,  # LocalCheckpoint or SupabaseCheckpoint instance
) -> AnalysisState:
    """
    Run the full 8-agent analysis pipeline.

    Args:
        ticker: Stock ticker symbol (e.g. "NVDA")
        trade_date: Analysis date as "YYYY-MM-DD"
        analyst_provider: LLM provider for Phase 1 analysts (default: google)
        analyst_model: Model for Phase 1 (default: gemini-2.5-flash -- fast + cheap)
        synthesis_provider: LLM provider for Phase 2+3 (default: anthropic)
        synthesis_model: Model for Phase 2+3 (default: claude-sonnet-4-6 -- quality)
        portfolio_context: Dict of {TICKER: {shares, avg_cost_usd}} for personalization
        on_agent_complete: Async callback fired after each agent completes
        selected_analysts: Which Phase 1 analysts to run

    Returns:
        AnalysisState with all reports and final_decision populated
    """
    from tradingagents.default_config import DEFAULT_CONFIG
    analyst_provider = analyst_provider or DEFAULT_CONFIG["analyst_provider"]
    analyst_model = analyst_model or DEFAULT_CONFIG["analyst_model"]
    synthesis_provider = synthesis_provider or DEFAULT_CONFIG["synthesis_provider"]
    synthesis_model = synthesis_model or DEFAULT_CONFIG["synthesis_model"]

    # Resume from checkpoint if available (crash recovery)
    if checkpoint is not None:
        prior = checkpoint.load()
        if prior is not None:
            logger.info("Resuming from checkpoint for %s (%d agents done)", ticker, len(prior.completed_agents))
            state = prior
        else:
            state = AnalysisState(
                ticker=ticker.upper(),
                trade_date=trade_date,
                portfolio_context=portfolio_context or {},
            )
    else:
        state = AnalysisState(
            ticker=ticker.upper(),
            trade_date=trade_date,
            portfolio_context=portfolio_context or {},
        )

    async def notify(agent_name: str) -> None:
        if on_agent_complete:
            try:
                await on_agent_complete(agent_name, state)
            except Exception as e:
                logger.warning("on_agent_complete callback failed for %s: %s", agent_name, e)
        # Save checkpoint after each agent completes
        if checkpoint is not None:
            checkpoint.save(state)

    # ── Phase 1: Analyst agents in parallel ──────────────────────────────────
    analyst_tasks = []
    analyst_names = []

    if "fundamentals" in selected_analysts:
        analyst_tasks.append(run_fundamental_analyst(state, analyst_provider, analyst_model))
        analyst_names.append("fundamentals")

    if "market" in selected_analysts:
        analyst_tasks.append(run_market_analyst(state, analyst_provider, analyst_model))
        analyst_names.append("market")

    if "news" in selected_analysts:
        analyst_tasks.append(run_news_analyst(state, analyst_provider, analyst_model))
        analyst_names.append("news")

    if "social" in selected_analysts:
        analyst_tasks.append(run_sentiment_analyst(state, analyst_provider, analyst_model))
        analyst_names.append("social")

    if analyst_tasks:
        logger.info("Phase 1: running %d analysts in parallel for %s", len(analyst_tasks), ticker)
        results = await asyncio.gather(*analyst_tasks, return_exceptions=True)

        for name, result in zip(analyst_names, results):
            if isinstance(result, Exception):
                logger.error("Analyst %s failed: %s", name, result)
                result = f"Analysis unavailable: {result}"
            if name == "fundamentals":
                state.fundamentals_report = result
            elif name == "market":
                state.market_report = result
            elif name == "news":
                state.news_report = result
            elif name == "social":
                state.sentiment_report = result
            await notify(name.title() + " Analyst")

    # ── Phase 2: Researchers in parallel ─────────────────────────────────────
    logger.info("Phase 2: running bull + bear researchers in parallel for %s", ticker)
    bull_result, bear_result = await asyncio.gather(
        run_bull_researcher(state, synthesis_provider, synthesis_model),
        run_bear_researcher(state, synthesis_provider, synthesis_model),
        return_exceptions=True,
    )

    if isinstance(bull_result, Exception):
        logger.error("Bull researcher failed: %s", bull_result)
        bull_result = f"Bull analysis unavailable: {bull_result}"
    if isinstance(bear_result, Exception):
        logger.error("Bear researcher failed: %s", bear_result)
        bear_result = f"Bear analysis unavailable: {bear_result}"

    state.bull_case = bull_result
    state.bear_case = bear_result
    state.debate_history = f"{bull_result}\n\n{bear_result}"
    await notify("Bull Researcher")
    await notify("Bear Researcher")

    # ── Phase 3: Sequential synthesis ────────────────────────────────────────
    logger.info("Phase 3: sequential synthesis for %s", ticker)

    try:
        state.investment_plan = await run_research_manager(state, synthesis_provider, synthesis_model)
        await notify("Research Manager")
    except Exception as e:
        logger.error("Research Manager failed: %s", e)
        state.investment_plan = f"Research plan unavailable: {e}"

    try:
        state.trader_proposal = await run_trader(state, synthesis_provider, synthesis_model)
        await notify("Trader")
    except Exception as e:
        logger.error("Trader failed: %s", e)
        state.trader_proposal = f"Trader proposal unavailable: {e}"

    try:
        state.final_decision = await run_portfolio_manager(state, synthesis_provider, synthesis_model)
        await notify("Portfolio Manager")
    except Exception as e:
        logger.error("Portfolio Manager failed: %s", e)
        state.final_decision = f"Decision unavailable: {e}"

    logger.info(
        "Analysis complete for %s: %d/8 agents", ticker, len(state.completed_agents)
    )
    # Clear checkpoint on successful completion
    if checkpoint is not None:
        checkpoint.clear()

    return state


# ── Convenience sync wrapper for CLI use ─────────────────────────────────────

def run_analysis_sync(ticker: str, trade_date: str, **kwargs) -> AnalysisState:
    """Synchronous wrapper for use in CLI and scripts."""
    return asyncio.run(run_analysis(ticker, trade_date, **kwargs))
