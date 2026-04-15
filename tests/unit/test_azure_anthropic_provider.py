"""Unit tests for the Azure Anthropic provider."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from src.agent.providers.azure_anthropic import (
    AzureAnthropicProvider,
    _merge_consecutive_user_messages,
)
from src.agent.providers.base import ToolCall


@pytest.fixture
def settings():
    return SimpleNamespace(
        azure_anthropic_endpoint="https://test-foundry.services.ai.azure.com/anthropic",
        azure_anthropic_api_key="test-key",
        azure_anthropic_deployment="claude-opus-4-6",
        azure_openai_api_key="fallback-key",
    )


@pytest.fixture
def provider(settings):
    return AzureAnthropicProvider(settings)


class TestSystemPromptExtraction:
    def test_extracts_system_from_input_items(self, provider):
        items = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "system", "content": "Additional context."},
            {"role": "user", "content": "Hello"},
        ]
        system, messages = provider._extract_system_and_messages(items)
        assert system == "You are a helpful assistant.\n\nAdditional context."
        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": "Hello"}

    def test_converts_function_call_output_to_tool_result(self, provider):
        items = [
            {"type": "function_call_output", "call_id": "tc_1", "output": "result text"},
        ]
        _, messages = provider._extract_system_and_messages(items)
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"][0]["type"] == "tool_result"
        assert messages[0]["content"][0]["tool_use_id"] == "tc_1"


class TestToolSchemaConversion:
    def test_converts_openai_to_anthropic_format(self, provider):
        openai_schemas = [
            {
                "name": "search",
                "description": "Search notes",
                "type": "function",
                "strict": True,
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"],
                    "additionalProperties": False,
                },
            }
        ]
        result = provider.format_tool_schemas(openai_schemas)
        assert len(result) == 1
        assert result[0]["name"] == "search"
        assert result[0]["description"] == "Search notes"
        assert "input_schema" in result[0]
        assert "type" not in result[0] or result[0].get("type") != "function"
        assert "strict" not in result[0]
        assert "parameters" not in result[0]
        assert result[0]["input_schema"]["type"] == "object"


class TestFormatToolResult:
    def test_returns_anthropic_tool_result_format(self, provider):
        tc = ToolCall(call_id="tc_123", name="search", arguments="{}")
        result = provider.format_tool_result(tc, "found 3 notes")
        assert result["role"] == "user"
        assert result["content"][0]["type"] == "tool_result"
        assert result["content"][0]["tool_use_id"] == "tc_123"
        assert result["content"][0]["content"] == "found 3 notes"


class TestConsecutiveUserMessageMerging:
    def test_merges_adjacent_user_messages(self):
        messages = [
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "a"}]},
            {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "2", "content": "b"}]},
        ]
        merged = _merge_consecutive_user_messages(messages)
        assert len(merged) == 1
        assert len(merged[0]["content"]) == 2

    def test_does_not_merge_different_roles(self):
        messages = [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "bye"},
        ]
        merged = _merge_consecutive_user_messages(messages)
        assert len(merged) == 3

    def test_normalizes_string_content_to_blocks(self):
        messages = [
            {"role": "user", "content": "first"},
            {"role": "user", "content": "second"},
        ]
        merged = _merge_consecutive_user_messages(messages)
        assert len(merged) == 1
        assert merged[0]["content"] == [
            {"type": "text", "text": "first"},
            {"type": "text", "text": "second"},
        ]

    def test_empty_list(self):
        assert _merge_consecutive_user_messages([]) == []


class TestResponseParsing:
    @pytest.mark.asyncio
    async def test_parses_text_response(self, provider):
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Hello there!")],
        )
        with patch.object(provider, "_create_message", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.generate([{"role": "user", "content": "Hi"}])
        assert result.text == "Hello there!"
        assert result.tool_calls == []

    @pytest.mark.asyncio
    async def test_parses_tool_use_response(self, provider):
        mock_response = SimpleNamespace(
            content=[
                SimpleNamespace(
                    type="tool_use",
                    id="tu_abc",
                    name="search",
                    input={"query": "meetings"},
                ),
            ],
        )
        with patch.object(provider, "_create_message", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.generate(
                [{"role": "user", "content": "find meetings"}],
                tools=[{"name": "search", "description": "Search", "input_schema": {}}],
            )
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.call_id == "tu_abc"
        assert tc.name == "search"
        assert json.loads(tc.arguments) == {"query": "meetings"}

    @pytest.mark.asyncio
    async def test_raw_output_items_structure(self, provider):
        mock_response = SimpleNamespace(
            content=[
                SimpleNamespace(type="text", text="Let me search."),
                SimpleNamespace(type="tool_use", id="tu_1", name="search", input={"q": "x"}),
            ],
        )
        with patch.object(provider, "_create_message", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.generate([{"role": "user", "content": "search"}])
        assert len(result.raw_output_items) == 1
        assert result.raw_output_items[0]["role"] == "assistant"
        assert len(result.raw_output_items[0]["content"]) == 2


class TestSummarize:
    @pytest.mark.asyncio
    async def test_summarize_calls_generate(self, provider):
        mock_response = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="Summary of conversation.")],
        )
        with patch.object(provider, "_create_message", new_callable=AsyncMock, return_value=mock_response):
            result = await provider.summarize("User asked about meetings.")
        assert result == "Summary of conversation."


class TestApiKeyFallback:
    def test_falls_back_to_openai_key(self):
        s = SimpleNamespace(
            azure_anthropic_endpoint="https://example.com/anthropic",
            azure_anthropic_api_key="",
            azure_anthropic_deployment="claude-opus-4-6",
            azure_openai_api_key="fallback-key",
        )
        provider = AzureAnthropicProvider(s)
        assert provider._client.api_key == "fallback-key"
