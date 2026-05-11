"""LiteLLM-based provider factory — drop-in replacement for LangChain LLM clients.

Supports all providers TradingAgents previously supported via LangChain:
  openai, anthropic, google, deepseek, qwen, glm, openrouter, azure, ollama
"""
from __future__ import annotations
import os
from typing import Any

import litellm
from litellm import acompletion

# Map provider names to LiteLLM model prefix
_PROVIDER_PREFIX = {
    "openai":     "",           # gpt-4o -> gpt-4o
    "anthropic":  "anthropic/", # claude-sonnet-4-6 -> anthropic/claude-sonnet-4-6
    "google":     "gemini/",    # gemini-2.5-flash -> gemini/gemini-2.5-flash
    "deepseek":   "deepseek/",
    "qwen":       "openrouter/qwen/",
    "glm":        "openrouter/zhipuai/",
    "openrouter": "openrouter/",
    "azure":      "azure/",
    "ollama":     "ollama/",
    "xai":        "xai/",
}


def model_id(provider: str, model_name: str) -> str:
    """Construct the LiteLLM model string from provider + model name."""
    prefix = _PROVIDER_PREFIX.get(provider.lower(), "")
    if model_name.startswith(prefix):
        return model_name  # already prefixed
    return f"{prefix}{model_name}"


async def llm_call(
    provider: str,
    model_name: str,
    system: str,
    user: str,
    tools: list | None = None,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str:
    """Single LLM call returning the text response.

    Handles tool use automatically — if tools are provided and the model
    requests a tool call, executes the tool and sends a follow-up message.
    """
    mid = model_id(provider, model_name)
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    kwargs: dict[str, Any] = {
        "model": mid,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    # Retry once on transient 503/502 errors (Gemini occasionally blips)
    for attempt in range(2):
        try:
            response = await acompletion(**kwargs)
            break
        except Exception as e:
            if attempt == 0 and ("503" in str(e) or "502" in str(e) or "unavailable" in str(e).lower()):
                import asyncio as _asyncio
                await _asyncio.sleep(3)
                continue
            raise
    if not response.choices:
        return ""
    msg = response.choices[0].message

    # Handle tool calls if the model requested them
    if tools and msg.tool_calls:
        from tradingagents.pipeline.tools import execute_tool_call
        tool_results = []
        for tc in msg.tool_calls:
            result = await execute_tool_call(tc.function.name, tc.function.arguments)
            tool_results.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })
        # Follow-up call with tool results
        messages.append({"role": "assistant", "content": None, "tool_calls": msg.tool_calls})
        messages.extend(tool_results)
        kwargs["messages"] = messages
        del kwargs["tools"]
        del kwargs["tool_choice"]
        response = await acompletion(**kwargs)
        if not response.choices:
            return ""
        msg = response.choices[0].message

    return msg.content or ""


async def llm_structured(
    provider: str,
    model_name: str,
    system: str,
    user: str,
    schema: type,
) -> Any:
    """LLM call that returns a parsed Pydantic model instance.

    Uses LiteLLM's response_format for structured output where supported,
    falls back to JSON extraction from free text.
    """
    import json
    from pydantic import ValidationError

    mid = model_id(provider, model_name)

    # Append JSON instruction to system prompt
    schema_json = json.dumps(schema.model_json_schema(), indent=2)
    system_with_schema = (
        f"{system}\n\n"
        f"Respond ONLY with valid JSON matching this schema:\n{schema_json}"
    )

    try:
        response = await acompletion(
            model=mid,
            messages=[
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2048,
        )
        text = response.choices[0].message.content or "{}"
        data = json.loads(text)
        return schema(**data)
    except Exception:
        # Fallback: extract JSON from free text
        text = await llm_call(provider, model_name, system_with_schema, user)
        # Find JSON block
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return schema(**json.loads(match.group()))
            except (json.JSONDecodeError, ValidationError, TypeError):
                pass
        # Last resort: return None so caller can use prose fallback
        return None
