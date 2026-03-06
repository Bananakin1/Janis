"""Unit tests for the tool registry and core tool contracts."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from src.adapters.base import AgentRequest
from src.backend.vault_index import VaultIndex
from src.tools.base import ToolContext
from src.tools.registry import ToolRegistry


class DummyREST:
    async def read_note(self, path: str):
        return f"content for {path}"

    async def search_simple(self, query: str, context_length: int = 100):
        return [{"filename": "Agent.md", "matches": [{"context": "agent context"}]}]


@pytest.fixture
def registry() -> ToolRegistry:
    return ToolRegistry.discover()


@pytest.fixture
def ctx(tmp_path) -> ToolContext:
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "Agent.md").write_text("# Agent\n")
    index = VaultIndex(vault_path)
    index.refresh()
    settings = SimpleNamespace(default_note_folder="Inbox")
    return ToolContext(
        settings=settings,
        rest=DummyREST(),
        cli=None,
        vault_index=index,
        request=AgentRequest(user_id="u1", user_name="User", message="hello"),
        memory=None,
    )


class TestRegistryDiscovery:
    def test_discovers_expected_tools(self, registry: ToolRegistry):
        names = set(registry.names())
        assert {"search_notes", "read_note", "upsert_note", "ask_clarification"} <= names
        assert "delete_note" in names
        assert "set_property" in names

    def test_schemas_use_responses_api_shape(self, registry: ToolRegistry):
        schemas = registry.get_schemas()
        search = next(schema for schema in schemas if schema["name"] == "search_notes")
        assert search["type"] == "function"
        assert search["strict"] is True
        assert "parameters" in search
        assert search["parameters"]["type"] == "object"

    def test_cli_tools_hidden_without_context(self, registry: ToolRegistry):
        schemas = registry.get_schemas()
        names = {schema["name"] for schema in schemas}
        assert "move_note" not in names
        assert "set_property" not in names


class TestRegistryExecution:
    @pytest.mark.asyncio
    async def test_executes_search_tool(self, registry: ToolRegistry, ctx: ToolContext):
        result = await registry.execute("search_notes", {"query": "agent"}, ctx)
        assert "Agent.md" in result.content

    @pytest.mark.asyncio
    async def test_clarification_tool_stops_loop(self, registry: ToolRegistry, ctx: ToolContext):
        result = await registry.execute(
            "ask_clarification",
            {
                "ambiguous_term": "agent",
                "matches": ["Agent.md", "SPEC-agent-planner.md"],
                "question": "Which agent note did you mean?",
            },
            ctx,
        )
        assert result.stop is True
        assert result.response is not None
        assert result.response.action is not None
        assert len(result.response.action.options) == 2

    @pytest.mark.asyncio
    async def test_delete_tool_requires_confirmation(self, registry: ToolRegistry, ctx: ToolContext):
        result = await registry.execute("delete_note", {"path": "Agent.md"}, ctx)
        assert result.stop is True
        assert result.response is not None
        assert result.response.action is not None
