"""Backward-compatible create/update tool with prepend support."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import ToolModel, prepend_to_note, resolve_note_path
from src.tools.base import ToolContext, ToolDefinition


class UpsertNoteParams(ToolModel):
    """Parameters for note upserts."""

    note_name: str = Field(
        ...,
        description="Note name or vault-relative path for the target note.",
    )
    content: str = Field(..., description="Markdown content to create or write.")
    folder: str | None = Field(
        default=None,
        description="Target folder when creating a new note by note name instead of path.",
    )
    prepend: bool | None = Field(
        default=None,
        description="When true, prepend the provided dated block before the first date section.",
    )


async def execute(params: UpsertNoteParams, ctx: ToolContext) -> str:
    if "/" in params.note_name or params.note_name.endswith(".md"):
        note_path = resolve_note_path(params.note_name, ctx.vault_index)
    elif ctx.vault_index.get_note_path(params.note_name) is not None:
        note_path = resolve_note_path(params.note_name, ctx.vault_index)
    else:
        folder = (params.folder or ctx.settings.default_note_folder).strip("/")
        note_path = f"{folder}/{params.note_name}.md"

    if params.prepend:
        existing = await ctx.rest.read_note(note_path)
        merged = prepend_to_note(existing or "", params.content)
        await ctx.rest.upsert_note(note_path, merged)
        return f"Prepended content to '{note_path}'."

    await ctx.rest.upsert_note(note_path, params.content)
    return f"Upserted note '{note_path}'."


tool = ToolDefinition(
    name="upsert_note",
    description="Create a new note or update an existing note, with optional prepend mode for dated sections.",
    params_model=UpsertNoteParams,
    execute=execute,
)
