"""Eight analysis agents as pure async functions.

Pipeline phases:
  Phase 1 (parallel):  fundamental, market, news, sentiment analysts
  Phase 2 (parallel):  bull researcher, bear researcher
  Phase 3 (sequential): research manager -> trader -> portfolio manager
"""
from __future__ import annotations
import logging
from tradingagents.pipeline.state import AnalysisState
from tradingagents.pipeline.llm import llm_call, llm_structured
from tradingagents.pipeline.tools import (
    FUNDAMENTAL_TOOLS, MARKET_TOOLS, NEWS_TOOLS, SENTIMENT_TOOLS
)

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────────

def _base_system(role_prompt: str) -> str:
    return (
        "You are a helpful AI assistant collaborating with other analysts. "
        "Use the provided tools to progress towards answering the question. "
        "Execute what you can to make progress. "
        f"{role_prompt}"
    )

# ── Phase 1: Analyst agents (run in parallel) ──────────────────────────────

async def run_fundamental_analyst(state: AnalysisState, provider: str, model: str) -> str:
    system = _base_system(
        "You are a researcher tasked with analyzing fundamental information about a company. "
        "Write a comprehensive report of the company's fundamental information such as financial "
        "documents, company profile, basic company financials, and company financial history. "
        "Include as much detail as possible. Provide specific, actionable insights with supporting "
        "evidence. Append a Markdown table at the end organizing key points."
        + state.portfolio_context_str()
    )
    user = (
        f"Analyze the fundamentals of {state.ticker} as of {state.trade_date}. "
        f"Use get_fundamentals, get_balance_sheet, get_cashflow, and get_income_statement."
    )
    report = await llm_call(provider, model, system, user, tools=FUNDAMENTAL_TOOLS, max_tokens=3000)
    state.mark_complete("Fundamental Analyst", f"Financial analysis of {state.ticker} complete")
    return report


async def run_market_analyst(state: AnalysisState, provider: str, model: str) -> str:
    system = _base_system(
        "You are a trading assistant tasked with analyzing financial markets. "
        "Select the most relevant technical indicators for the given market condition. "
        "Choose up to 8 indicators that provide complementary insights without redundancy. "
        "Call get_stock_data first to retrieve price data, then get_indicators with specific "
        "indicator names (rsi, macd, macds, macdh, boll, boll_ub, boll_lb, close_50_sma, "
        "close_200_sma, close_10_ema, atr, vwma). Write a detailed and nuanced report of "
        "the trends you observe. Append a Markdown table at the end."
        + state.portfolio_context_str()
    )
    user = (
        f"Analyze the technical indicators for {state.ticker} as of {state.trade_date}. "
        f"First call get_stock_data, then get_indicators with the most relevant indicators."
    )
    report = await llm_call(provider, model, system, user, tools=MARKET_TOOLS, max_tokens=3000)
    state.mark_complete("Technical Analyst", f"Technical analysis of {state.ticker} complete")
    return report


async def run_news_analyst(state: AnalysisState, provider: str, model: str) -> str:
    system = _base_system(
        "You are a news researcher tasked with analyzing recent news and trends over the past week. "
        "Write a comprehensive report of the current state of the world relevant for trading and "
        "macroeconomics. Use get_news for company-specific or targeted news, and get_global_news "
        "for broader macroeconomic news. Provide specific, actionable insights. "
        "Append a Markdown table at the end."
        + state.portfolio_context_str()
    )
    user = (
        f"Research and analyze news relevant to {state.ticker} as of {state.trade_date}. "
        f"Cover both company-specific news and relevant macroeconomic events."
    )
    report = await llm_call(provider, model, system, user, tools=NEWS_TOOLS, max_tokens=3000)
    state.mark_complete("News Analyst", f"News analysis for {state.ticker} complete")
    return report


async def run_sentiment_analyst(state: AnalysisState, provider: str, model: str) -> str:
    system = _base_system(
        "You are a social media and company-specific news researcher/analyst tasked with analyzing "
        "social media posts, recent company news, and public sentiment for a specific company over "
        "the past week. Write a comprehensive report detailing analysis, insights, and implications "
        "for traders on the company's current state. Look at social media, sentiment data, and "
        "recent company news. Provide specific, actionable insights. "
        "Append a Markdown table at the end."
        + state.portfolio_context_str()
    )
    user = (
        f"Analyze social media sentiment and public opinion for {state.ticker} as of {state.trade_date}. "
        f"Use get_news to search for social discussions and sentiment."
    )
    report = await llm_call(provider, model, system, user, tools=SENTIMENT_TOOLS, max_tokens=3000)
    state.mark_complete("Sentiment Analyst", f"Sentiment analysis for {state.ticker} complete")
    return report

# ── Phase 2: Researcher debate (run in parallel) ───────────────────────────

async def run_bull_researcher(state: AnalysisState, provider: str, model: str) -> str:
    system = (
        "You are a Bull Analyst advocating for investing in the stock. Build a strong, "
        "evidence-based case emphasizing growth potential, competitive advantages, and positive "
        "market indicators. Key points: Growth Potential (market opportunities, revenue projections, "
        "scalability), Competitive Advantages (unique products, branding, market positioning), "
        "Positive Indicators (financial health, industry trends, recent positive news). "
        "Present your argument conversationally, engaging directly with the data."
        + state.portfolio_context_str()
    )
    user = (
        f"Build the bull case for {state.ticker} as of {state.trade_date}.\n\n"
        f"Market analysis:\n{state.market_report}\n\n"
        f"Sentiment:\n{state.sentiment_report}\n\n"
        f"News:\n{state.news_report}\n\n"
        f"Fundamentals:\n{state.fundamentals_report}"
    )
    report = await llm_call(provider, model, system, user, max_tokens=2000)
    state.mark_complete("Bull Researcher", f"Bull case for {state.ticker} constructed")
    return f"Bull Analyst: {report}"


async def run_bear_researcher(state: AnalysisState, provider: str, model: str) -> str:
    system = (
        "You are a Bear Analyst making the case against investing in the stock. Build a rigorous, "
        "evidence-based argument highlighting risks, overvaluation concerns, competitive threats, "
        "and negative indicators. Key points: Risk Factors (market risks, execution challenges), "
        "Valuation Concerns (stretched multiples, priced for perfection), Competitive Threats "
        "(emerging competitors, market share erosion), Negative Indicators (weakening metrics, "
        "sector headwinds). Be analytical and direct."
        + state.portfolio_context_str()
    )
    user = (
        f"Build the bear case for {state.ticker} as of {state.trade_date}.\n\n"
        f"Market analysis:\n{state.market_report}\n\n"
        f"Sentiment:\n{state.sentiment_report}\n\n"
        f"News:\n{state.news_report}\n\n"
        f"Fundamentals:\n{state.fundamentals_report}"
    )
    report = await llm_call(provider, model, system, user, max_tokens=2000)
    state.mark_complete("Bear Researcher", f"Bear case for {state.ticker} constructed")
    return f"Bear Analyst: {report}"

# ── Phase 3: Synthesis (sequential) ───────────────────────────────────────

async def run_research_manager(state: AnalysisState, provider: str, model: str) -> str:
    from tradingagents.agents.schemas import ResearchPlan, render_research_plan

    system = (
        "You are the Research Manager and debate facilitator. Critically evaluate the bull/bear "
        "debate and deliver a clear, actionable investment plan for the trader.\n\n"
        "Rating Scale (use exactly one):\n"
        "- Buy: Strong conviction in the bull thesis\n"
        "- Overweight: Constructive view, gradually increase exposure\n"
        "- Hold: Balanced view, maintain current position\n"
        "- Underweight: Cautious view, trim exposure\n"
        "- Sell: Strong conviction in the bear thesis\n\n"
        "Commit to a clear stance whenever the debate warrants one. Reserve Hold for "
        "genuinely balanced evidence."
        + state.portfolio_context_str()
    )
    debate = f"Bull argument:\n{state.bull_case}\n\nBear argument:\n{state.bear_case}"
    user = (
        f"Evaluate the debate for {state.ticker} as of {state.trade_date} and produce "
        f"a structured investment plan.\n\n{debate}"
    )

    result = await llm_structured(provider, model, system, user, ResearchPlan)
    if result:
        plan_text = render_research_plan(result)
    else:
        plan_text = await llm_call(provider, model, system, user, max_tokens=2000)

    state.mark_complete("Research Manager", f"Investment plan for {state.ticker} produced")
    return plan_text


async def run_trader(state: AnalysisState, provider: str, model: str) -> str:
    from tradingagents.agents.schemas import TraderProposal, render_trader_proposal

    system = (
        "You are a trading agent analyzing market data to make investment decisions. "
        "Based on the research plan, provide a specific recommendation to buy, sell, or hold. "
        "Anchor your reasoning in the analysts' reports and the research plan. "
        "Be decisive and specific."
        + state.portfolio_context_str()
    )
    user = (
        f"Based on the following investment plan for {state.ticker}, produce a concrete "
        f"transaction proposal.\n\nInvestment Plan:\n{state.investment_plan}"
    )

    result = await llm_structured(provider, model, system, user, TraderProposal)
    if result:
        proposal = render_trader_proposal(result)
    else:
        proposal = await llm_call(provider, model, system, user, max_tokens=1000)

    state.mark_complete("Trader", f"Transaction proposal for {state.ticker} produced")
    return proposal


async def run_portfolio_manager(state: AnalysisState, provider: str, model: str) -> str:
    from tradingagents.agents.schemas import PortfolioDecision, render_pm_decision

    system = (
        "You are the Portfolio Manager. Synthesize the research and trader proposal into the "
        "final trading decision.\n\n"
        "Rating Scale (use exactly one):\n"
        "- Buy: Strong conviction to enter or add to position\n"
        "- Overweight: Favorable outlook, gradually increase exposure\n"
        "- Hold: Maintain current position\n"
        "- Underweight: Reduce exposure\n"
        "- Sell: Exit position\n\n"
        "Be decisive and ground every conclusion in specific evidence."
        + state.portfolio_context_str()
    )
    user = (
        f"Produce the final trading decision for {state.ticker} as of {state.trade_date}.\n\n"
        f"Research Manager's plan:\n{state.investment_plan}\n\n"
        f"Trader's proposal:\n{state.trader_proposal}"
    )

    result = await llm_structured(provider, model, system, user, PortfolioDecision)
    if result:
        decision = render_pm_decision(result)
    else:
        decision = await llm_call(provider, model, system, user, max_tokens=1500)

    state.mark_complete("Portfolio Manager", f"Final decision for {state.ticker}: complete")
    return decision
