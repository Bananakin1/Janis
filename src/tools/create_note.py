"""Tool for creating a new note."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import PathToolModel, ensure_markdown_path
from src.tools.base import ToolContext, ToolDefinition


class CreateNoteParams(PathToolModel):
    """Parameters for note creation."""

    content: str = Field(..., description="Markdown content for the new note.")


async def execute(params: CreateNoteParams, ctx: ToolContext) -> str:
    note_path = ensure_markdown_path(params.path)
    existing = await ctx.rest.read_note(note_path)
    if existing is not None:
        return f"Note '{note_path}' already exists."
    await ctx.rest.upsert_note(note_path, params.content)
    return f"Created note '{note_path}'."


tool = ToolDefinition(
    name="create_note",
    description="Create a new note at a specific vault-relative path. Fails if the note exists.",
    params_model=CreateNoteParams,
    execute=execute,
)
