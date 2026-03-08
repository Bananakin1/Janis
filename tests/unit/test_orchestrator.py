"""Unit tests for the provider-agnostic orchestrator."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, Field

from src.adapters.base import AgentResponse
from src.agent.orchestrator import Orchestrator
from src.tools._shared import DATE_HEADING_RE, prepend_to_note
from src.agent.providers.base import ProviderResponse, ToolCall
from src.backend.vault_index import VaultIndex
from src.tools.base import ToolContext, ToolDefinition, ToolResult
from src.tools.registry import ToolRegistry


class DummyRestClient:
    def __init__(self, *_args, healthy: bool = True, **_kwargs):
        self.healthy = healthy

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def health_check(self) -> bool:
        return self.healthy

    async def read_note(self, path: str):
        return None


class DummyProvider:
    def __init__(self, responses):
        self._responses = list(responses)
        self.inputs = []

    async def generate(self, input_items, *, tools=None):
        self.inputs.append((input_items, tools))
        return self._responses.pop(0)

    async def summarize(self, conversation_text: str) -> str:
        return "summary"

    def format_tool_result(self, tool_call, output):
        return {"type": "function_call_output", "call_id": tool_call.call_id, "output": output}

    def format_tool_schemas(self, schemas):
        return schemas


class EchoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = Field(...)


async def _echo_tool(params: EchoParams, ctx: ToolContext) -> ToolResult:
    return ToolResult(content=f"echo:{params.value}")


async def _stop_tool(params: EchoParams, ctx: ToolContext) -> ToolResult:
    return ToolResult(
        content="need input",
        stop=True,
        response=AgentResponse(text=f"Choose {params.value}"),
    )


@pytest.fixture
def settings(tmp_path):
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    return SimpleNamespace(
        obsidian_vault_path=vault_path,
        obsidian_api_url="https://127.0.0.1:27124",
        obsidian_api_key="test-key",
        azure_openai_endpoint="https://test.openai.azure.com",
        azure_openai_api_key="test-key",
        azure_openai_deployment="gpt-4o",
        llm_provider="azure_openai",
        obsidian_cli_command="obsidian",
        default_note_folder="Inbox",
        reasoning_effort="medium",
        memory_db_path=tmp_path / "memory.db",
        memory_summary_interval=10,
        max_tool_iterations=4,
        prompt_cache_ttl_seconds=60,
        vault_conventions_note_path="Vault Conventions",
        tag_registry_note_path="Tag Registry",
    )


def _make_orchestrator(settings, provider, registry=None, rest_client_cls=DummyRestClient):
    vault_index = VaultIndex(settings.obsidian_vault_path)
    return Orchestrator(
        settings,
        provider=provider,
        registry=registry or ToolRegistry.discover(),
        rest_client_cls=rest_client_cls,
        vault_index=vault_index,
    )


class TestHelpers:
    def test_date_heading_regex(self):
        assert DATE_HEADING_RE.match("## 01/01/2026")
        assert not DATE_HEADING_RE.match("# Not a date heading")

    def test_prepend_to_note_inserts_before_first_date(self):
        content = "# Note\n\n## 01/01/2026\nOld"
        updated = prepend_to_note(content, "## 02/01/2026\nNew")
        assert "## 02/01/2026" in updated
        assert updated.index("## 02/01/2026") < updated.index("## 01/01/2026")


class TestProcessMessage:
    @pytest.mark.asyncio
    async def test_returns_offline_message_when_obsidian_unavailable(self, settings):
        class OfflineRestClient(DummyRestClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, healthy=False, **kwargs)

        orch = _make_orchestrator(settings, provider=DummyProvider([]), rest_client_cls=OfflineRestClient)
        assert "Obsidian is not running" in await orch.process_message("hello")

    @pytest.mark.asyncio
    async def test_returns_provider_text_without_tools(self, settings):
        provider = DummyProvider([ProviderResponse(text="done")])
        orch = _make_orchestrator(settings, provider=provider)

        result = await orch.process_message("hello", author="User")

        assert result == "done"
        messages = orch._memory.get_recent_messages("User")
        assert len(messages) == 2
        assert messages[0].content == "hello"
        assert messages[1].content == "done"

    @pytest.mark.asyncio
    async def test_executes_registry_tools_then_returns_final_text(self, settings):
        registry = ToolRegistry(
            [
                ToolDefinition(
                    name="echo_tool",
                    description="Echoes a value.",
                    params_model=EchoParams,
                    execute=_echo_tool,
                )
            ]
        )
        provider = DummyProvider(
            [
                ProviderResponse(
                    text="",
                    tool_calls=[ToolCall(call_id="1", name="echo_tool", arguments=json.dumps({"value": "x"}))],
                    raw_output_items=[{"type": "function_call", "call_id": "1", "name": "echo_tool", "arguments": '{"value": "x"}'}],
                ),
                ProviderResponse(text="final"),
            ]
        )
        orch = _make_orchestrator(settings, provider=provider, registry=registry)

        result = await orch.process_message("use tool", author="User")

        assert result == "final"
        assert len(provider.inputs) == 2
        second_input_items = provider.inputs[1][0]
        assert any(item.get("type") == "function_call_output" and item.get("output") == "echo:x" for item in second_input_items)

    @pytest.mark.asyncio
    async def test_stop_tool_short_circuits_loop(self, settings):
        registry = ToolRegistry(
            [
                ToolDefinition(
                    name="stop_tool",
                    description="Stops and returns a response.",
                    params_model=EchoParams,
                    execute=_stop_tool,
                )
            ]
        )
        provider = DummyProvider(
            [
                ProviderResponse(
                    text="",
                    tool_calls=[ToolCall(call_id="1", name="stop_tool", arguments=json.dumps({"value": "A"}))],
                    raw_output_items=[],
                ),
            ]
        )
        orch = _make_orchestrator(settings, provider=provider, registry=registry)

        result = await orch.process_message("stop", author="User")

        assert result == "Choose A"
        assert orch.last_agent_response is not None
        assert orch.last_agent_response.text == "Choose A"

    @pytest.mark.asyncio
    async def test_check_health_success(self, settings):
        orch = _make_orchestrator(settings, provider=DummyProvider([]))
        healthy, error = await orch.check_health()
        assert healthy is True
        assert error is None
