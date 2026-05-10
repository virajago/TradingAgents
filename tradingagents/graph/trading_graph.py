"""Backward compatibility shim — delegates to tradingagents.pipeline.runner.

All public methods of the original TradingAgentsGraph are preserved so that
CLI scripts and tests that import from this module continue to work unchanged.
The LangGraph-based implementation is replaced by the asyncio pipeline.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.pipeline.runner import run_analysis_sync
from tradingagents.pipeline.state import AnalysisState

logger = logging.getLogger(__name__)


class TradingAgentsGraph:
    """Drop-in replacement for the LangGraph-based TradingAgentsGraph.

    Delegates to the new asyncio pipeline. All public methods are preserved
    for CLI and script compatibility.
    """

    def __init__(
        self,
        selected_analysts: List[str] = None,
        debug: bool = False,
        config: Optional[Dict[str, Any]] = None,
        callbacks: Optional[List] = None,
        user_id: str = "cli",
        supabase_client=None,
    ):
        if selected_analysts is None:
            selected_analysts = ["market", "social", "news", "fundamentals"]

        self.config = config or DEFAULT_CONFIG.copy()
        self.debug = debug
        self.user_id = user_id
        self.selected_analysts = list(selected_analysts)
        self._supabase = supabase_client

        # Create necessary directories
        os.makedirs(self.config.get("data_cache_dir", "."), exist_ok=True)
        os.makedirs(self.config.get("results_dir", "."), exist_ok=True)

        # Memory log: Postgres for SaaS, file-based for CLI
        if supabase_client is not None:
            from tradingagents.agents.utils.postgres_memory import PostgresMemoryLog
            self.memory_log = PostgresMemoryLog(user_id=user_id, supabase_client=supabase_client)
        else:
            from tradingagents.agents.utils.memory import TradingMemoryLog
            self.memory_log = TradingMemoryLog(config=self.config)

        # Shim state — populated by propagate()
        self.curr_state: Optional[AnalysisState] = None
        self.ticker: Optional[str] = None

    def propagate(self, ticker: str, trade_date: str) -> Tuple[Dict[str, Any], str]:
        """Synchronous analysis run — returns (state_dict, final_decision_str).

        Matches the original API: callers unpack the two-tuple directly.
        """
        from tradingagents.dataflows.config import set_config
        set_config(self.config)

        self.ticker = ticker

        state = run_analysis_sync(
            ticker,
            trade_date,
            analyst_provider=self.config.get("analyst_provider", "google"),
            analyst_model=self.config.get("analyst_model", "gemini-2.5-flash"),
            synthesis_provider=self.config.get("synthesis_provider", "anthropic"),
            synthesis_model=self.config.get("synthesis_model", "claude-sonnet-4-6"),
            portfolio_context=self.config.get("portfolio_context"),
            selected_analysts=self.selected_analysts,
        )

        self.curr_state = state

        # Store decision for deferred reflection on the next same-ticker run.
        self.memory_log.store_decision(
            ticker=ticker,
            trade_date=trade_date,
            final_trade_decision=state.final_decision,
        )

        signal = self.process_signal(state.final_decision)

        state_dict = {
            "company_of_interest": ticker,
            "trade_date": trade_date,
            "market_report": state.market_report,
            "sentiment_report": state.sentiment_report,
            "news_report": state.news_report,
            "fundamentals_report": state.fundamentals_report,
            "investment_plan": state.investment_plan,
            "trader_investment_plan": state.trader_proposal,
            "final_trade_decision": state.final_decision,
        }

        return state_dict, signal

    def process_signal(self, full_signal: str) -> str:
        """Extract the core decision signal from the full decision text."""
        if not full_signal:
            return "HOLD"
        upper = full_signal.upper()
        for keyword in ("BUY", "SELL", "HOLD"):
            if keyword in upper:
                return keyword
        return full_signal.strip()
