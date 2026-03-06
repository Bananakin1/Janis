"""Tool for opening a note in Obsidian."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import PathToolModel, ensure_markdown_path
from src.tools.base import ToolContext, ToolDefinition


class OpenNoteParams(PathToolModel):
    """Parameters for open note operations."""


async def execute(params: OpenNoteParams, ctx: ToolContext) -> str:
    note_path = ensure_markdown_path(params.path)
    await ctx.rest.open_note(note_path)
    return f"Opened '{note_path}'."


tool = ToolDefinition(
    name="open_note",
    description="Open a note in the running Obsidian client.",
    params_model=OpenNoteParams,
    execute=execute,
)
