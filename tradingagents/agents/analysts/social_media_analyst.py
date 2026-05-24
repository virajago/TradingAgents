from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.agent_utils import build_instrument_context, get_language_instruction, get_news
from tradingagents.agents.utils.sentiment_data_tools import (
    get_stocktwits_messages,
    get_reddit_posts,
)
from tradingagents.dataflows.config import get_config


def create_social_media_analyst(llm):
    def social_media_analyst_node(state):
        current_date = state["trade_date"]
        instrument_context = build_instrument_context(state["company_of_interest"])

        tools = [
            get_news,
            get_stocktwits_messages,
            get_reddit_posts,
        ]

        system_message = (
            "You are a sentiment and social-media analyst tasked with assessing retail "
            "investor sentiment, social-media discussion, and public perception of a "
            "specific company over the past week. Your objective is to write a "
            "comprehensive report with concrete signal-vs-noise reasoning that helps "
            "traders interpret what the crowd is saying.\n\n"
            "You have three data sources — use them complementarily, not redundantly:\n"
            "  • get_stocktwits_messages(ticker) — recent StockTwits messages with "
            "user-labeled Bullish/Bearish sentiment. Best for raw retail positioning "
            "and tone of conviction.\n"
            "  • get_reddit_posts(ticker) — recent discussion across r/wallstreetbets, "
            "r/stocks, r/investing. Best for narrative themes, due diligence threads, "
            "and identifying viral catalysts.\n"
            "  • get_news(ticker, start_date, end_date) — formal news coverage. Best "
            "for grounding social sentiment in actual events.\n\n"
            "Synthesize across sources: where do retail traders and the news agree or "
            "disagree? Are bullish/bearish StockTwits ratios consistent with Reddit "
            "narrative? Highlight any sentiment-vs-fundamentals divergence as a key "
            "signal. Provide specific, actionable insights with supporting evidence."
            + """ Make sure to append a Markdown table at the end of the report to organize key points in the report, organized and easy to read."""
            + get_language_instruction()
        )

        prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "You are a helpful AI assistant, collaborating with other assistants."
                    " Use the provided tools to progress towards answering the question."
                    " If you are unable to fully answer, that's OK; another assistant with different tools"
                    " will help where you left off. Execute what you can to make progress."
                    " If you or any other assistant has the FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** or deliverable,"
                    " prefix your response with FINAL TRANSACTION PROPOSAL: **BUY/HOLD/SELL** so the team knows to stop."
                    " You have access to the following tools: {tool_names}.\n{system_message}"
                    "For your reference, the current date is {current_date}. {instrument_context}",
                ),
                MessagesPlaceholder(variable_name="messages"),
            ]
        )

        prompt = prompt.partial(system_message=system_message)
        prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
        prompt = prompt.partial(current_date=current_date)
        prompt = prompt.partial(instrument_context=instrument_context)

        chain = prompt | llm.bind_tools(tools)

        result = chain.invoke(state["messages"])

        report = ""

        if len(result.tool_calls) == 0:
            report = result.content

        return {
            "messages": [result],
            "sentiment_report": report,
        }

    return social_media_analyst_node
