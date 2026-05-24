"""LangChain tool wrappers for social-sentiment data sources.

Wraps the underlying dataflow fetchers (StockTwits public stream,
Reddit public search) so the social media / sentiment analyst can
call them via the standard tool-binding flow. Both sources use
public endpoints and degrade gracefully on failure, so the analyst
never has to special-case missing data.
"""

from langchain_core.tools import tool
from typing import Annotated

from tradingagents.dataflows.stocktwits import fetch_stocktwits_messages
from tradingagents.dataflows.reddit import fetch_reddit_posts


@tool
def get_stocktwits_messages(
    ticker: Annotated[str, "Ticker symbol"],
    limit: Annotated[int, "Max messages to return (default 30)"] = 30,
) -> str:
    """
    Retrieve recent StockTwits messages for a ticker with user-labeled
    sentiment (Bullish/Bearish/null). Uses the public symbol-stream
    endpoint; no API key required.

    Args:
        ticker (str): Ticker symbol (case-insensitive)
        limit (int): Maximum number of messages to return

    Returns:
        str: Formatted plaintext block of recent messages, or a placeholder
             string when the symbol has no messages or the endpoint is
             unreachable.
    """
    return fetch_stocktwits_messages(ticker, limit=limit)


@tool
def get_reddit_posts(
    ticker: Annotated[str, "Ticker symbol"],
) -> str:
    """
    Retrieve recent Reddit posts (last 7 days) mentioning a ticker across
    finance subreddits (wallstreetbets, stocks, investing). Uses Reddit's
    public JSON search endpoints; no API key required.

    Args:
        ticker (str): Ticker symbol (case-insensitive)

    Returns:
        str: Formatted plaintext block of recent posts grouped by
             subreddit, or a placeholder string when no posts are found
             or the endpoint is unreachable.
    """
    return fetch_reddit_posts(ticker)
