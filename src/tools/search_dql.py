"""Tool for Dataview DQL search."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import ToolModel, format_search_payload
from src.tools.base import ToolContext, ToolDefinition


class SearchDQLParams(ToolModel):
    """Parameters for structured vault search."""

    query: str = Field(..., description="Raw Dataview DQL query to execute.")


async def execute(params: SearchDQLParams, ctx: ToolContext) -> str:
    payload = await ctx.rest.search_dql(params.query)
    return format_search_payload(payload)


tool = ToolDefinition(
    name="search_dql",
    description="Run a Dataview DQL query against the vault for structured search.",
    params_model=SearchDQLParams,
    execute=execute,
)
