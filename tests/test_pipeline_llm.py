"""Tests for LiteLLM provider factory (model_id)."""
import pytest
from tradingagents.pipeline.llm import model_id


def test_model_id_anthropic_prefix():
    assert model_id("anthropic", "claude-sonnet-4-6") == "anthropic/claude-sonnet-4-6"


def test_model_id_google_prefix():
    assert model_id("google", "gemini-2.5-flash") == "gemini/gemini-2.5-flash"


def test_model_id_openai_no_prefix():
    """OpenAI models have an empty prefix — model name is passed through unchanged."""
    result = model_id("openai", "gpt-4o")
    assert result == "gpt-4o"


def test_model_id_deepseek_prefix():
    assert model_id("deepseek", "deepseek-chat") == "deepseek/deepseek-chat"


def test_model_id_already_prefixed_not_doubled():
    """If the model already has the provider prefix, it must not be doubled."""
    result = model_id("anthropic", "anthropic/claude-sonnet-4-6")
    assert result == "anthropic/claude-sonnet-4-6"
    assert "anthropic/anthropic" not in result


def test_model_id_ollama_prefix():
    assert model_id("ollama", "llama3") == "ollama/llama3"


def test_model_id_azure_prefix():
    assert model_id("azure", "gpt-4o") == "azure/gpt-4o"


def test_model_id_openrouter_prefix():
    assert model_id("openrouter", "meta-llama/llama-3") == "openrouter/meta-llama/llama-3"


def test_model_id_xai_prefix():
    assert model_id("xai", "grok-3") == "xai/grok-3"


def test_model_id_qwen_prefix():
    assert model_id("qwen", "qwen-max") == "openrouter/qwen/qwen-max"


def test_model_id_glm_prefix():
    assert model_id("glm", "glm-4") == "openrouter/zhipuai/glm-4"


def test_model_id_unknown_provider_passthrough():
    """Unknown providers have an empty prefix — model name is passed through."""
    result = model_id("unknown_provider", "some-model")
    assert "some-model" in result


def test_model_id_provider_case_insensitive():
    """Provider name lookup is case-insensitive."""
    upper = model_id("ANTHROPIC", "claude-sonnet-4-6")
    lower = model_id("anthropic", "claude-sonnet-4-6")
    assert upper == lower


def test_model_id_google_already_prefixed():
    """Gemini models that already include the 'gemini/' prefix are not doubled."""
    result = model_id("google", "gemini/gemini-2.5-flash")
    assert result == "gemini/gemini-2.5-flash"
    assert "gemini/gemini/gemini" not in result
