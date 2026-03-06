"""Tool for setting frontmatter properties via the Obsidian CLI."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import PathToolModel
from src.tools.base import ToolContext, ToolDefinition


class SetPropertyParams(PathToolModel):
    """Parameters for frontmatter property updates."""

    key: str = Field(..., description="Frontmatter property name to set.")
    value: str = Field(..., description="Frontmatter property value to set.")


async def execute(params: SetPropertyParams, ctx: ToolContext) -> str:
    return await ctx.cli.set_property(params.path, params.key, params.value)


tool = ToolDefinition(
    name="set_property",
    description="Set a frontmatter property on a note using the Obsidian CLI.",
    params_model=SetPropertyParams,
    execute=execute,
    requires_cli=True,
)
