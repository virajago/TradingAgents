"""Async analysis runner: wraps TradingAgentsGraph with concurrency control and task tracking."""
import asyncio
import logging
from typing import Optional

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph

logger = logging.getLogger(__name__)

# Global semaphore — max 20 concurrent analyses (matches Settings.max_concurrent_analyses)
_semaphore = asyncio.Semaphore(20)

# In-memory task store (single Cloud Run instance for Phase 1A).
# Key: task_id (UUID string). Value: task state dict.
_tasks: dict[str, dict] = {}

AGENT_NAMES = [
    "Fundamental Analyst",
    "Sentiment Analyst",
    "News Analyst",
    "Technical Analyst",
    "Bull Researcher",
    "Bear Researcher",
    "Research Manager",
    "Portfolio Manager",
]


async def run_analysis(
    task_id: str,
    ticker: str,
    user_id: str,
    trade_date: str,
    config_overrides: Optional[dict] = None,
    portfolio_context: Optional[dict] = None,
) -> None:
    """
    Run a full TradingAgents analysis for a single (ticker, date) pair.

    Updates _tasks[task_id] with progress so callers can poll /status.
    Errors are caught and surfaced in task["error"]; they do not propagate.
    """
    _tasks[task_id] = {
        "status": "running",
        "ticker": ticker,
        "trade_date": trade_date,
        "user_id": user_id,
        "agents": [{"name": n, "status": "queued", "summary": None} for n in AGENT_NAMES],
        "progress_pct": 0,
        "result": None,
        "error": None,
    }

    async with _semaphore:
        try:
            # Build per-request config
            config = DEFAULT_CONFIG.copy()
            # On-demand: use quality models
            config["deep_think_llm"] = "claude-sonnet-4-6"
            config["quick_think_llm"] = "gemini-2.5-flash"
            config["llm_provider"] = "anthropic"

            if config_overrides:
                config.update(config_overrides)

            # Portfolio context injected via config (Phase 1B: use as system prompt prefix)
            if portfolio_context:
                config["portfolio_context"] = portfolio_context

            # Phase 1A: mark each agent "running" sequentially as we progress,
            # yielding to the event loop so /status polls stay responsive.
            # Phase 1B will hook into LangGraph node callbacks for true per-agent updates.
            for i in range(len(AGENT_NAMES) - 1):
                _tasks[task_id]["agents"][i]["status"] = "running"
                _tasks[task_id]["progress_pct"] = int((i / len(AGENT_NAMES)) * 90)
                await asyncio.sleep(0)  # yield to event loop

            # Run the actual analysis in the thread pool (blocking I/O + LLM calls)
            loop = asyncio.get_event_loop()
            ta = TradingAgentsGraph(
                debug=False,
                config=config,
            )

            _, decision = await loop.run_in_executor(
                None,
                lambda: ta.propagate(ticker, trade_date),
            )

            # Mark all agents complete
            for i in range(len(AGENT_NAMES)):
                _tasks[task_id]["agents"][i]["status"] = "complete"
            _tasks[task_id]["progress_pct"] = 100
            _tasks[task_id]["status"] = "complete"
            _tasks[task_id]["result"] = decision

            logger.info("Analysis complete: task=%s ticker=%s", task_id, ticker)

        except Exception:
            logger.exception("Analysis failed: task=%s ticker=%s", task_id, ticker)
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["error"] = f"Analysis failed for {ticker}"
            # Mark all non-complete agents as errored for UI clarity
            for agent in _tasks[task_id]["agents"]:
                if agent["status"] != "complete":
                    agent["status"] = "error"


def get_task(task_id: str) -> Optional[dict]:
    """Return task state dict, or None if unknown."""
    return _tasks.get(task_id)
