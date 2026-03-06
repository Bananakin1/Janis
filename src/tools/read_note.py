"""Tool for reading a note."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import ToolModel, resolve_note_path
from src.tools.base import ToolContext, ToolDefinition


class ReadNoteParams(ToolModel):
    """Parameters for note reads."""

    note_name: str = Field(
        ...,
        description="Note name without extension or a vault-relative path.",
    )


async def execute(params: ReadNoteParams, ctx: ToolContext) -> str:
    note_path = resolve_note_path(params.note_name, ctx.vault_index)
    content = await ctx.rest.read_note(note_path)
    if content is None:
        return f"Note '{params.note_name}' not found."
    return content


tool = ToolDefinition(
    name="read_note",
    description="Read the full contents of an existing note.",
    params_model=ReadNoteParams,
    execute=execute,
)
