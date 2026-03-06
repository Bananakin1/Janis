"""Integration tests for the refactored orchestrator."""

import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, ConfigDict, Field

from src.adapters.base import AgentRequest
from src.agent.orchestrator import Orchestrator
from src.agent.providers.base import ProviderResponse, ToolCall
from src.backend.vault_index import VaultIndex
from src.tools.base import ToolContext, ToolDefinition, ToolResult
from src.tools.registry import ToolRegistry


class FakeRestClient:
    def __init__(self, *_args, **_kwargs):
        self.upserts = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def health_check(self):
        return True

    async def read_note(self, path: str):
        if path == "Vault Conventions.md":
            return "Keep meeting notes in 05 Meetings."
        if path == "Tag Registry.md":
            return "#meeting\n#spec"
        return None

    async def upsert_note(self, path: str, content: str):
        self.upserts.append((path, content))
        return True


class FakeProvider:
    def __init__(self, responses):
        self.responses = list(responses)

    async def generate(self, input_items, *, tools=None):
        return self.responses.pop(0)

    async def summarize(self, conversation_text: str) -> str:
        return "summary"


class WriteParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(...)
    content: str = Field(...)


async def _write_tool(params: WriteParams, ctx: ToolContext) -> ToolResult:
    await ctx.rest.upsert_note(params.path, params.content)
    return ToolResult(content=f"Wrote {params.path}")


@pytest.fixture
def settings(temp_vault, tmp_path):
    return SimpleNamespace(
        obsidian_vault_path=temp_vault,
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


@pytest.mark.asyncio
async def test_orchestrator_persists_memory_across_messages(settings):
    provider = FakeProvider(
        [
            ProviderResponse(text="Read Curinos"),
            ProviderResponse(text="Using the same note"),
        ]
    )
    orchestrator = Orchestrator(
        settings,
        provider=provider,
        rest_client_cls=FakeRestClient,
        vault_index=VaultIndex(settings.obsidian_vault_path),
    )

    await orchestrator.process_request(AgentRequest(user_id="u1", user_name="User", message="Read Curinos"))
    await orchestrator.process_request(AgentRequest(user_id="u1", user_name="User", message="Add to that note"))

    messages = orchestrator._memory.get_recent_messages("u1")
    assert len(messages) == 4
    assert messages[0].content == "Read Curinos"
    assert messages[2].content == "Add to that note"


@pytest.mark.asyncio
async def test_orchestrator_executes_registry_tool(settings):
    registry = ToolRegistry(
        [
            ToolDefinition(
                name="write_tool",
                description="Writes a note.",
                params_model=WriteParams,
                execute=_write_tool,
            )
        ]
    )
    provider = FakeProvider(
        [
            ProviderResponse(
                text="",
                tool_calls=[
                    ToolCall(
                        call_id="1",
                        name="write_tool",
                        arguments=json.dumps({"path": "Inbox/Test.md", "content": "hello"}),
                    )
                ],
                raw_output_items=[],
            ),
            ProviderResponse(text="done"),
        ]
    )
    orchestrator = Orchestrator(
        settings,
        provider=provider,
        registry=registry,
        rest_client_cls=FakeRestClient,
        vault_index=VaultIndex(settings.obsidian_vault_path),
    )

    result = await orchestrator.process_request(
        AgentRequest(user_id="u1", user_name="User", message="write")
    )

    assert result.text == "done"
