"""Tool for simple note search."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import ToolModel, format_search_payload
from src.tools.base import ToolContext, ToolDefinition


class SearchNotesParams(ToolModel):
    """Parameters for simple note search."""

    query: str = Field(..., description="Text query to search note names and contents.")
    context_length: int = Field(
        default=100,
        ge=0,
        le=1000,
        description="Characters of surrounding match context to return.",
    )


async def execute(params: SearchNotesParams, ctx: ToolContext) -> str:
    results = await ctx.rest.search_simple(params.query, context_length=params.context_length)
    if not results:
        return "No matching notes found."
    return f"Found {len(results)} result(s):\n{format_search_payload(results[:20])}"


tool = ToolDefinition(
    name="search_notes",
    description="Search notes in the vault by name or content and return matching files.",
    params_model=SearchNotesParams,
    execute=execute,
)
