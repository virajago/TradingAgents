"""Tool definitions for LiteLLM tool use — wraps existing dataflow functions."""
from __future__ import annotations
import json
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Tool schemas (OpenAI function-calling format) ─────────────────────────────

FUNDAMENTAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fundamentals",
            "description": "Get comprehensive company fundamentals including profile and financials",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "Stock ticker symbol"},
                    "curr_date": {"type": "string", "description": "Current date YYYY-MM-DD"},
                },
                "required": ["ticker", "curr_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_balance_sheet",
            "description": "Get company balance sheet data",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "curr_date": {"type": "string"},
                },
                "required": ["ticker", "curr_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cashflow",
            "description": "Get company cash flow statement",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "curr_date": {"type": "string"},
                },
                "required": ["ticker", "curr_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_income_statement",
            "description": "Get company income statement",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "curr_date": {"type": "string"},
                },
                "required": ["ticker", "curr_date"],
            },
        },
    },
]

MARKET_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stock_data",
            "description": "Get historical OHLCV stock price data as CSV",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["ticker", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicators",
            "description": "Get technical indicators for a stock",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "curr_date": {"type": "string"},
                    "indicators": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of indicator names: rsi, macd, boll, close_50_sma, etc.",
                    },
                },
                "required": ["ticker", "curr_date", "indicators"],
            },
        },
    },
]

NEWS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Search for company-specific news and social media discussions",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["query", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_global_news",
            "description": "Get broader macroeconomic and global news",
            "parameters": {
                "type": "object",
                "properties": {
                    "curr_date": {"type": "string"},
                    "look_back_days": {"type": "integer", "default": 7},
                    "limit": {"type": "integer", "default": 20},
                },
                "required": ["curr_date"],
            },
        },
    },
]

SENTIMENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Search for social media discussions and company-specific news",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "start_date": {"type": "string"},
                    "end_date": {"type": "string"},
                },
                "required": ["query", "start_date", "end_date"],
            },
        },
    },
]


# ── Tool executor ─────────────────────────────────────────────────────────────

async def execute_tool_call(name: str, arguments_json: str) -> Any:
    """Execute a tool by name with JSON arguments. Returns string result."""
    try:
        args = json.loads(arguments_json)
    except json.JSONDecodeError:
        return f"Error: invalid JSON arguments for {name}"

    try:
        loop = asyncio.get_event_loop()

        if name == "get_fundamentals":
            from tradingagents.agents.utils.agent_utils import get_fundamentals
            result = await loop.run_in_executor(None, lambda: get_fundamentals.invoke(args))
        elif name == "get_balance_sheet":
            from tradingagents.agents.utils.agent_utils import get_balance_sheet
            result = await loop.run_in_executor(None, lambda: get_balance_sheet.invoke(args))
        elif name == "get_cashflow":
            from tradingagents.agents.utils.agent_utils import get_cashflow
            result = await loop.run_in_executor(None, lambda: get_cashflow.invoke(args))
        elif name == "get_income_statement":
            from tradingagents.agents.utils.agent_utils import get_income_statement
            result = await loop.run_in_executor(None, lambda: get_income_statement.invoke(args))
        elif name == "get_stock_data":
            from tradingagents.agents.utils.agent_utils import get_stock_data
            result = await loop.run_in_executor(None, lambda: get_stock_data.invoke(args))
        elif name == "get_indicators":
            from tradingagents.agents.utils.agent_utils import get_indicators
            result = await loop.run_in_executor(None, lambda: get_indicators.invoke(args))
        elif name == "get_news":
            from tradingagents.agents.utils.agent_utils import get_news
            result = await loop.run_in_executor(None, lambda: get_news.invoke(args))
        elif name == "get_global_news":
            from tradingagents.agents.utils.agent_utils import get_global_news
            result = await loop.run_in_executor(None, lambda: get_global_news.invoke(args))
        else:
            return f"Unknown tool: {name}"

        return str(result)[:8000]  # cap to avoid context overflow

    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        return f"Tool {name} error: {e}"
