"""Tool for moving notes via the Obsidian CLI."""

from __future__ import annotations

from pydantic import Field, field_validator

from src.backend.rest_client import validate_vault_path
from src.tools._shared import ToolModel
from src.tools.base import ToolContext, ToolDefinition


class MoveNoteParams(ToolModel):
    """Parameters for note move operations."""

    source: str = Field(..., description="Current vault-relative path of the note.")
    destination: str = Field(..., description="Target vault-relative path for the note.")

    @field_validator("source", "destination")
    @classmethod
    def _validate_paths(cls, value: str) -> str:
        return validate_vault_path(value)


async def execute(params: MoveNoteParams, ctx: ToolContext) -> str:
    return await ctx.cli.move(params.source, params.destination)


tool = ToolDefinition(
    name="move_note",
    description="Move or rename a note using the Obsidian CLI so wikilinks update correctly.",
    params_model=MoveNoteParams,
    execute=execute,
    requires_cli=True,
)
