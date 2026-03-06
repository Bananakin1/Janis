"""Tool for directory browsing."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import ToolModel
from src.tools.base import ToolContext, ToolDefinition


class ListVaultParams(ToolModel):
    """Parameters for listing a vault directory."""

    path: str | None = Field(
        default=None,
        description="Optional vault-relative directory path to list.",
    )


async def execute(params: ListVaultParams, ctx: ToolContext) -> str:
    items = await ctx.rest.list_vault(params.path)
    if not items:
        return "No notes found."
    return "\n".join(str(item) for item in items)


tool = ToolDefinition(
    name="list_vault",
    description="List notes and folders inside a vault directory.",
    params_model=ListVaultParams,
    execute=execute,
)
