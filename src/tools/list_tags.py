"""Tool for listing tags known to the Obsidian CLI."""

from __future__ import annotations

import json

from src.tools._shared import ToolModel
from src.tools.base import ToolContext, ToolDefinition


class ListTagsParams(ToolModel):
    """No-argument model for tag listing."""


async def execute(params: ListTagsParams, ctx: ToolContext) -> str:
    tags = await ctx.cli.list_tags()
    return json.dumps(tags, indent=2, sort_keys=True)


tool = ToolDefinition(
    name="list_tags",
    description="List tag frequencies from the vault via the Obsidian CLI.",
    params_model=ListTagsParams,
    execute=execute,
    requires_cli=True,
)
