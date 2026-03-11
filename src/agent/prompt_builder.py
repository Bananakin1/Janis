"""Dynamic system prompt generation."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from src.backend.vault_index import VaultIndex
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

_FALLBACK_CONTENT = "Not available."
_NO_TOOLS = "No tool preference guidance configured."
_MAX_INJECTION_CHARS = 4000

SYSTEM_PROMPT_TEMPLATE = """You are Janis, an Obsidian vault agent operating on behalf of a knowledge worker.

<rules>
- NEVER fabricate note paths or content. Use search results and read_note output only.
- NEVER call update_note or upsert_note on an existing note you have not read in this conversation.
- NEVER set delete_note confirmed=true unless the user explicitly confirmed deletion in the current turn.
- NEVER echo raw tool output (JSON, search payloads, full note dumps) to the user. Summarize.
- Read existing notes before replacing them.
- Ask for clarification when references are ambiguous.
- Conventions and tag registry are already provided below — do not re-read them.
- You have a budget of {max_iterations} tool calls per request. Plan accordingly.
- Keep final responses under 300 words unless the user asked for full note content.
- When presenting search results, summarize the top 5 matches and mention total count if more exist.
</rules>

<environment>
- Date: {today}
- Vault notes: {total_notes}
- Folders: {folders}
- Recent notes: {recent_notes}
- Folder counts: {folder_counts}
- Default folder for new notes: {default_folder}
</environment>

<tool_preferences>
Prefer the most targeted tool for the job:
- read/write today's daily note: use daily_read / daily_append (not manual path construction)
- targeted section edit: use patch_note (not update_note)
- full note replacement: use update_note (read first, merge changes)
- new note (known to not exist): use create_note (fails safely if it already exists)
- new note (may already exist): use upsert_note
- add a dated entry to a meeting note: use upsert_note with prepend=true (meeting notes use reverse chronological order — newest date heading first)
- append to end of note: use append_note
- keyword lookup: use search_notes
- structured query (frontmatter properties, date ranges, sorting): use search_dql
- move/rename with wikilink updates: use move_note (CLI required)
- frontmatter property change: use set_property (CLI) or patch_note with target_type=frontmatter (REST)
</tool_preferences>

<conventions>
{conventions}
</conventions>

<tag_registry>
{tag_registry}
</tag_registry>
"""


@dataclass(slots=True)
class _CachedNote:
    content: str | None = None
    expires_at: datetime | None = None


@dataclass(slots=True)
class _PromptCache:
    notes: dict[str, _CachedNote] = field(default_factory=dict)


def _truncate(content: str, max_chars: int = _MAX_INJECTION_CHARS) -> str:
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + "\n[truncated]"


class PromptBuilder:
    """Builds a system prompt from live vault state and cached conventions."""

    def __init__(self, settings, registry: ToolRegistry, cache_ttl_seconds: int = 300) -> None:
        self._settings = settings
        self._registry = registry
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._cache = _PromptCache()

    def _is_cached(self, path: str) -> bool:
        entry = self._cache.notes.get(path)
        if entry is None or entry.content is None or entry.expires_at is None:
            return False
        return entry.expires_at > datetime.now(UTC)

    def _get_cached(self, path: str) -> str | None:
        if self._is_cached(path):
            return self._cache.notes[path].content
        return None

    def _set_cached(self, path: str, content: str) -> None:
        self._cache.notes[path] = _CachedNote(
            content=content,
            expires_at=datetime.now(UTC) + self._cache_ttl,
        )

    async def _read_both_notes(self, rest_client) -> tuple[str, str]:
        conv_path = self._settings.vault_conventions_note_path
        tag_path = self._settings.tag_registry_note_path

        conv_cached = self._get_cached(conv_path)
        tag_cached = self._get_cached(tag_path)

        if conv_cached is not None and tag_cached is not None:
            return conv_cached, tag_cached

        # Fetch uncached notes concurrently
        tasks = []
        fetch_conv = conv_cached is None
        fetch_tag = tag_cached is None

        if fetch_conv:
            tasks.append(rest_client.read_note(conv_path))
        if fetch_tag:
            tasks.append(rest_client.read_note(tag_path))

        results = await asyncio.gather(*tasks) if tasks else []

        idx = 0
        if fetch_conv:
            content = results[idx] or _FALLBACK_CONTENT
            self._set_cached(conv_path, content)
            conv_cached = content
            idx += 1
        if fetch_tag:
            content = results[idx] or _FALLBACK_CONTENT
            self._set_cached(tag_path, content)
            tag_cached = content

        return conv_cached, tag_cached  # type: ignore[return-value]

    async def build(self, rest_client, vault_index: VaultIndex, tool_ctx=None) -> tuple[str, list[dict]]:
        """Build the system prompt and return (prompt, tool_schemas)."""
        vault_summary = vault_index.get_vault_summary()
        today = datetime.now().strftime("%m/%d/%Y")

        conventions, tag_registry = await self._read_both_notes(rest_client)
        schemas = self._registry.get_schemas(tool_ctx)
        fields = _format_vault_fields(vault_summary)

        default_folder = self._settings.default_note_folder
        max_iterations = self._settings.max_tool_iterations

        prompt = SYSTEM_PROMPT_TEMPLATE.format(
            today=today,
            conventions=_truncate(conventions),
            tag_registry=_truncate(tag_registry),
            default_folder=default_folder,
            max_iterations=max_iterations,
            **fields,
        )
        return prompt, schemas


def _format_vault_fields(vault_summary: dict) -> dict[str, str]:
    """Convert a vault summary dict into template-ready strings."""
    return {
        "folders": ", ".join(vault_summary.get("folders", [])) or "None",
        "recent_notes": ", ".join(vault_summary.get("recent_notes", [])) or "None",
        "folder_counts": ", ".join(
            f"{name or '(vault root)'}={count}"
            for name, count in sorted(vault_summary.get("folder_counts", {}).items())
        ) or "None",
        "total_notes": str(vault_summary.get("total_notes", 0)),
    }


def build_system_prompt(
    vault_summary: dict,
    conventions: str = _FALLBACK_CONTENT,
    tag_registry: str = _FALLBACK_CONTENT,
    tool_docs: str = "",
) -> str:
    """Backward-compatible helper used by tests."""
    fields = _format_vault_fields(vault_summary)
    return SYSTEM_PROMPT_TEMPLATE.format(
        today=datetime.now().strftime("%m/%d/%Y"),
        conventions=conventions,
        tag_registry=tag_registry,
        default_folder="Inbox",
        max_iterations=8,
        **fields,
    )
