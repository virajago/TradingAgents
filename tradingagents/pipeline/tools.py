"""Tool definitions for LiteLLM tool use — wraps existing dataflow functions.

Parameter names must exactly match what the LangChain @tool functions expect:
  get_stock_data(symbol, start_date, end_date)
  get_indicators(symbol, indicator, curr_date, look_back_days)
  get_fundamentals(ticker, curr_date)
  get_balance_sheet(ticker, curr_date)
  get_cashflow(ticker, curr_date)
  get_income_statement(ticker, curr_date)
  get_news(ticker, start_date, end_date)
  get_global_news(curr_date, look_back_days, limit)
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Tool schemas (OpenAI function-calling format) ─────────────────────────────

FUNDAMENTAL_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_fundamentals",
            "description": "Get comprehensive company fundamentals: financials, profile, key metrics",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker":    {"type": "string", "description": "Stock ticker symbol, e.g. NVDA"},
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
            "description": "Get company balance sheet (assets, liabilities, equity)",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker":    {"type": "string"},
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
                    "ticker":    {"type": "string"},
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
            "description": "Get company income statement (revenue, earnings, margins)",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker":    {"type": "string"},
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
                    # Function param is named 'symbol' — use that exact name
                    "symbol":     {"type": "string", "description": "Ticker symbol e.g. NVDA"},
                    "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                    "end_date":   {"type": "string", "description": "End date YYYY-MM-DD"},
                },
                "required": ["symbol", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_indicators",
            "description": (
                "Get a single technical indicator for a stock. Call once per indicator. "
                "Available: rsi, macd, macds, macdh, boll, boll_ub, boll_lb, "
                "close_50_sma, close_200_sma, close_10_ema, atr, vwma"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    # Function params: symbol, indicator (singular), curr_date, look_back_days
                    "symbol":        {"type": "string", "description": "Ticker symbol e.g. NVDA"},
                    "indicator":     {"type": "string", "description": "One indicator name e.g. rsi"},
                    "curr_date":     {"type": "string", "description": "Current date YYYY-MM-DD"},
                    "look_back_days":{"type": "integer", "description": "Days to look back", "default": 30},
                },
                "required": ["symbol", "indicator", "curr_date"],
            },
        },
    },
]

NEWS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_news",
            "description": "Search for company-specific news articles",
            "parameters": {
                "type": "object",
                "properties": {
                    # Function param is 'ticker' (not 'query')
                    "ticker":     {"type": "string", "description": "Ticker symbol e.g. NVDA"},
                    "start_date": {"type": "string", "description": "Start date YYYY-MM-DD"},
                    "end_date":   {"type": "string", "description": "End date YYYY-MM-DD"},
                },
                "required": ["ticker", "start_date", "end_date"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_global_news",
            "description": "Get broader macroeconomic and global market news",
            "parameters": {
                "type": "object",
                "properties": {
                    "curr_date":      {"type": "string", "description": "Current date YYYY-MM-DD"},
                    "look_back_days": {"type": "integer", "default": 7},
                    "limit":          {"type": "integer", "default": 20},
                },
                "required": ["curr_date"],
            },
        },
    },
]

# Sentiment analyst uses the same news tool (searches for company-specific discussion)
SENTIMENT_TOOLS = NEWS_TOOLS


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
            from tradingagents.agents.utils.fundamental_data_tools import get_fundamentals
            result = await loop.run_in_executor(None, lambda: get_fundamentals.invoke(args))

        elif name == "get_balance_sheet":
            from tradingagents.agents.utils.fundamental_data_tools import get_balance_sheet
            result = await loop.run_in_executor(None, lambda: get_balance_sheet.invoke(args))

        elif name == "get_cashflow":
            from tradingagents.agents.utils.fundamental_data_tools import get_cashflow
            result = await loop.run_in_executor(None, lambda: get_cashflow.invoke(args))

        elif name == "get_income_statement":
            from tradingagents.agents.utils.fundamental_data_tools import get_income_statement
            result = await loop.run_in_executor(None, lambda: get_income_statement.invoke(args))

        elif name == "get_stock_data":
            from tradingagents.agents.utils.core_stock_tools import get_stock_data
            # Normalise: LLM may send 'ticker' — function expects 'symbol'
            if "ticker" in args and "symbol" not in args:
                args["symbol"] = args.pop("ticker")
            result = await loop.run_in_executor(None, lambda: get_stock_data.invoke(args))

        elif name == "get_indicators":
            from tradingagents.agents.utils.technical_indicators_tools import get_indicators
            # Normalise: LLM may send 'ticker' — function expects 'symbol'
            if "ticker" in args and "symbol" not in args:
                args["symbol"] = args.pop("ticker")
            # Normalise: LLM may send 'indicators' (list) — call once per indicator
            if "indicators" in args and "indicator" not in args:
                indicators = args.pop("indicators")
                if isinstance(indicators, list):
                    parts = []
                    for ind in indicators:
                        call_args = {**args, "indicator": ind}
                        r = await loop.run_in_executor(None, lambda ca=call_args: get_indicators.invoke(ca))
                        parts.append(str(r))
                    result = "\n\n".join(parts)
                else:
                    args["indicator"] = indicators
                    result = await loop.run_in_executor(None, lambda: get_indicators.invoke(args))
            else:
                result = await loop.run_in_executor(None, lambda: get_indicators.invoke(args))

        elif name == "get_news":
            from tradingagents.agents.utils.news_data_tools import get_news
            # Normalise: LLM may send 'query' — function expects 'ticker'
            if "query" in args and "ticker" not in args:
                args["ticker"] = args.pop("query")
            result = await loop.run_in_executor(None, lambda: get_news.invoke(args))

        elif name == "get_global_news":
            from tradingagents.agents.utils.news_data_tools import get_global_news
            result = await loop.run_in_executor(None, lambda: get_global_news.invoke(args))

        else:
            return f"Unknown tool: {name}"

        return str(result)[:8000]  # cap to avoid context overflow

    except Exception as e:
        logger.error("Tool %s failed: %s", name, e)
        return f"Tool {name} error: {e}"
