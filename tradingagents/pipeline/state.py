"""Shared analysis state passed between agents."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Callable, Awaitable


@dataclass
class AnalysisState:
    """Accumulated state across the 8-agent pipeline."""
    ticker: str
    trade_date: str
    portfolio_context: dict = field(default_factory=dict)  # {ticker: {shares, avg_cost_usd}}

    # Phase 1: analyst reports (populated in parallel)
    market_report: str = ""
    sentiment_report: str = ""
    news_report: str = ""
    fundamentals_report: str = ""

    # Phase 2: researcher debate (populated in parallel)
    bull_case: str = ""
    bear_case: str = ""
    debate_history: str = ""

    # Phase 3: synthesis (sequential)
    investment_plan: str = ""      # Research Manager output
    trader_proposal: str = ""      # Trader output
    final_decision: str = ""       # Portfolio Manager output

    # Progress tracking for Briefing Room UI
    completed_agents: list = field(default_factory=list)
    agent_summaries: dict = field(default_factory=dict)  # name -> one-line summary

    def mark_complete(self, agent_name: str, summary: str = "") -> None:
        self.completed_agents.append(agent_name)
        if summary:
            self.agent_summaries[agent_name] = summary[:200]

    def portfolio_context_str(self) -> str:
        """Format portfolio holdings as a context string for agent prompts."""
        if not self.portfolio_context or self.ticker.upper() not in self.portfolio_context:
            return ""
        h = self.portfolio_context[self.ticker.upper()]
        shares = h.get("shares", 0)
        avg_cost = h.get("avg_cost_usd", 0)
        total = shares * avg_cost
        return (
            f"\n\nPORTFOLIO CONTEXT: The investor holds {shares} shares of {self.ticker.upper()} "
            f"at ${avg_cost:.2f} avg cost (${total:,.2f} total invested). "
            f"Factor this position into your analysis."
        )
