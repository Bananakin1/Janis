"""Tool for replacing a note's content."""

from __future__ import annotations

from pydantic import Field

from src.errors import ToolExecutionError
from src.tools._shared import PathToolModel, ensure_markdown_path
from src.tools.base import ToolContext, ToolDefinition


class UpdateNoteParams(PathToolModel):
    """Parameters for full note replacement."""

    content: str = Field(..., description="Complete replacement markdown content.")


async def execute(params: UpdateNoteParams, ctx: ToolContext) -> str:
    note_path = ensure_markdown_path(params.path)
    existing = await ctx.rest.read_note(note_path)
    if existing is None:
        raise ToolExecutionError(f"Cannot update missing note '{note_path}'.")
    await ctx.rest.upsert_note(note_path, params.content)
    return f"Updated note '{note_path}'."


tool = ToolDefinition(
    name="update_note",
    description="Replace the full contents of an existing note.",
    params_model=UpdateNoteParams,
    execute=execute,
)
