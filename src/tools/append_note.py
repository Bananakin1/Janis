"""Tool for appending to an existing note."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import PathToolModel, ensure_markdown_path
from src.tools.base import ToolContext, ToolDefinition


class AppendNoteParams(PathToolModel):
    """Parameters for append operations."""

    content: str = Field(..., description="Markdown content to append to the note.")


async def execute(params: AppendNoteParams, ctx: ToolContext) -> str:
    note_path = ensure_markdown_path(params.path)
    await ctx.rest.append_note(note_path, params.content)
    return f"Appended to '{note_path}'."


tool = ToolDefinition(
    name="append_note",
    description="Append content to the end of an existing note.",
    params_model=AppendNoteParams,
    execute=execute,
)
