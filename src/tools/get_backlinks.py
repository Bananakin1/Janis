"""Tool for retrieving backlinks."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import ToolModel
from src.tools.base import ToolContext, ToolDefinition


class GetBacklinksParams(ToolModel):
    """Parameters for backlink retrieval."""

    note_name: str = Field(
        ...,
        description="Note name or path to inspect for backlinks.",
    )


async def execute(params: GetBacklinksParams, ctx: ToolContext) -> str:
    if ctx.cli is not None and ctx.cli.is_available():
        backlinks = await ctx.cli.get_backlinks(params.note_name)
    else:
        backlinks = ctx.vault_index.get_backlinks(params.note_name)
    if not backlinks:
        return f"No backlinks found for '{params.note_name}'."
    return "\n".join(backlinks)


tool = ToolDefinition(
    name="get_backlinks",
    description="List notes that link to the target note.",
    params_model=GetBacklinksParams,
    execute=execute,
)
