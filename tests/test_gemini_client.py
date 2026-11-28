"""Unit tests cho adapter Gemini (OpenAI-compatible) và chuyển đổi LLM_PROVIDER."""

from types import SimpleNamespace

import pytest

from mcp_server.llm import groq as llm_mod


def test_create_gemini_client_requires_key(monkeypatch):
    monkeypatch.setattr(llm_mod, "load_dotenv", lambda: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        llm_mod.create_gemini_client()


def test_create_llm_client_switches_provider(monkeypatch):
    monkeypatch.setattr(llm_mod, "load_dotenv", lambda: None)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-test-key")
    client = llm_mod.create_llm_client()
    assert client._use_max_tokens is True
    assert str(client._api.base_url).startswith(llm_mod.GEMINI_BASE_URL)

    monkeypatch.setenv("LLM_PROVIDER", "invalid_provider")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        llm_mod.create_llm_client()


@pytest.mark.asyncio
async def test_gemini_client_sends_max_tokens():
    captured = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            msg = SimpleNamespace(content='{"ok": true}', tool_calls=[])
            return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")])

    fake_api = SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions()))
    client = llm_mod.GroqLLMClient(fake_api, use_max_tokens=True, model_override="gemini-2.5-pro")
    res = await client.create(
        model="openai/gpt-oss-120b", max_tokens=1000, temperature=0.0,
        system="sys", messages=[{"role": "user", "content": "hi"}], tools=[],
    )
    assert res.stop_reason == "end_turn"
    assert captured["model"] == "gemini-2.5-pro"
    assert captured["max_tokens"] == 8192
    assert "max_completion_tokens" not in captured
