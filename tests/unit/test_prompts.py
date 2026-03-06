"""Unit tests for prompt building."""

from types import SimpleNamespace

import pytest

from src.agent.prompt_builder import PromptBuilder, SYSTEM_PROMPT_TEMPLATE, build_system_prompt
from src.tools.registry import ToolRegistry


class DummyREST:
    async def read_note(self, path: str):
        if path == "Vault Conventions":
            return "Use 05 Meetings for meeting notes."
        if path == "Tag Registry":
            return "#meeting\n#spec"
        return None


class DummyVaultIndex:
    def get_vault_summary(self):
        return {
            "total_notes": 42,
            "folders": ["02 Specs", "05 Meetings"],
            "folder_counts": {"02 Specs": 10, "05 Meetings": 12},
            "recent_notes": ["SPEC-memory", "ITK"],
        }


def test_template_contains_dynamic_sections():
    assert "<environment>" in SYSTEM_PROMPT_TEMPLATE
    assert "<conventions>" in SYSTEM_PROMPT_TEMPLATE
    assert "<tag_registry>" in SYSTEM_PROMPT_TEMPLATE
    assert "<rules>" in SYSTEM_PROMPT_TEMPLATE
    assert "<tool_preferences>" in SYSTEM_PROMPT_TEMPLATE


def test_template_contains_anti_patterns():
    assert "NEVER fabricate" in SYSTEM_PROMPT_TEMPLATE
    assert "NEVER call update_note" in SYSTEM_PROMPT_TEMPLATE
    assert "NEVER set delete_note" in SYSTEM_PROMPT_TEMPLATE
    assert "NEVER echo raw tool output" in SYSTEM_PROMPT_TEMPLATE


def test_template_contains_constraints():
    assert "{max_iterations}" in SYSTEM_PROMPT_TEMPLATE
    assert "300 words" in SYSTEM_PROMPT_TEMPLATE
    assert "top 5" in SYSTEM_PROMPT_TEMPLATE


def test_template_contains_tool_preferences():
    assert "patch_note" in SYSTEM_PROMPT_TEMPLATE
    assert "create_note" in SYSTEM_PROMPT_TEMPLATE
    assert "search_dql" in SYSTEM_PROMPT_TEMPLATE
    assert "daily_read" in SYSTEM_PROMPT_TEMPLATE


def test_build_system_prompt_helper_formats_values():
    prompt = build_system_prompt(
        {"total_notes": 5, "folders": ["Inbox"], "recent_notes": ["A"], "folder_counts": {"Inbox": 5}},
        conventions="Conventions",
        tag_registry="Tags",
    )
    assert "5" in prompt
    assert "Inbox" in prompt
    assert "Conventions" in prompt
    assert "Tags" in prompt


def test_format_vault_fields_uses_vault_root_label():
    prompt = build_system_prompt(
        {"total_notes": 1, "folders": [], "recent_notes": [], "folder_counts": {"": 1}},
    )
    assert "(vault root)=1" in prompt
    assert "<root>" not in prompt


@pytest.mark.asyncio
async def test_prompt_builder_reads_conventions_and_tag_registry():
    settings = SimpleNamespace(
        vault_conventions_note_path="Vault Conventions",
        tag_registry_note_path="Tag Registry",
        default_note_folder="Inbox",
        max_tool_iterations=8,
    )
    builder = PromptBuilder(settings, ToolRegistry.discover(), cache_ttl_seconds=60)
    prompt, schemas = await builder.build(DummyREST(), DummyVaultIndex())
    assert "Use 05 Meetings for meeting notes." in prompt
    assert "#meeting" in prompt
    assert isinstance(schemas, list)
    assert len(schemas) > 0


@pytest.mark.asyncio
async def test_prompt_builder_returns_schemas():
    settings = SimpleNamespace(
        vault_conventions_note_path="Vault Conventions",
        tag_registry_note_path="Tag Registry",
        default_note_folder="Inbox",
        max_tool_iterations=8,
    )
    builder = PromptBuilder(settings, ToolRegistry.discover(), cache_ttl_seconds=60)
    _, schemas = await builder.build(DummyREST(), DummyVaultIndex())
    names = {s["name"] for s in schemas}
    assert "search_notes" in names
    assert "read_note" in names


@pytest.mark.asyncio
async def test_prompt_builder_truncates_large_content():
    class LargeREST:
        async def read_note(self, path: str):
            return "x" * 10_000

    settings = SimpleNamespace(
        vault_conventions_note_path="Vault Conventions",
        tag_registry_note_path="Tag Registry",
        default_note_folder="Inbox",
        max_tool_iterations=8,
    )
    builder = PromptBuilder(settings, ToolRegistry.discover(), cache_ttl_seconds=60)
    prompt, _ = await builder.build(LargeREST(), DummyVaultIndex())
    assert "[truncated]" in prompt


@pytest.mark.asyncio
async def test_prompt_builder_caches_per_note():
    call_count = 0

    class CountingREST:
        async def read_note(self, path: str):
            nonlocal call_count
            call_count += 1
            return f"content for {path}"

    settings = SimpleNamespace(
        vault_conventions_note_path="Vault Conventions",
        tag_registry_note_path="Tag Registry",
        default_note_folder="Inbox",
        max_tool_iterations=8,
    )
    builder = PromptBuilder(settings, ToolRegistry.discover(), cache_ttl_seconds=300)
    await builder.build(CountingREST(), DummyVaultIndex())
    assert call_count == 2  # conventions + tag_registry

    await builder.build(CountingREST(), DummyVaultIndex())
    assert call_count == 2  # both served from cache
