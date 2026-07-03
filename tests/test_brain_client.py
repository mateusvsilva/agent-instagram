from unittest.mock import AsyncMock, MagicMock
import pytest
from src.services.brain_client import OpenAIBrainClient, AnthropicBrainClient, build_brain_client


def _settings(**over):
    s = MagicMock()
    s.openai_api_key = over.get("openai_api_key", "sk-test")
    s.openai_brain_model = "gpt-4o-mini"
    s.anthropic_api_key = over.get("anthropic_api_key", "")
    s.brain_model = "claude-x"
    s.brain_provider = over.get("brain_provider", "openai")
    return s


def test_openai_available_reflects_key():
    assert OpenAIBrainClient(_settings()).available is True
    assert OpenAIBrainClient(_settings(openai_api_key="")).available is False


def test_factory_selects_provider():
    assert isinstance(build_brain_client(_settings(brain_provider="openai")), OpenAIBrainClient)
    assert isinstance(build_brain_client(_settings(brain_provider="anthropic")), AnthropicBrainClient)


async def test_openai_complete_extracts_text(monkeypatch):
    fake_msg = MagicMock()
    fake_msg.choices = [MagicMock(message=MagicMock(content="  hello  "))]
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=fake_msg)
    brain = OpenAIBrainClient(_settings())
    monkeypatch.setattr(brain, "_ensure_client", lambda: fake_client)
    out = await brain.complete("sys", "user", max_tokens=50)
    assert out == "hello"
