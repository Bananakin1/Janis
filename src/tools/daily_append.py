"""Tool for appending to today's daily note."""

from __future__ import annotations

from pydantic import Field

from src.tools._shared import ToolModel
from src.tools.base import ToolContext, ToolDefinition


class DailyAppendParams(ToolModel):
    """Parameters for daily note append operations."""

    content: str = Field(..., description="Content to append to today's daily note.")


async def execute(params: DailyAppendParams, ctx: ToolContext) -> str:
    await ctx.rest.append_daily(params.content)
    return "Appended to today's daily note."


tool = ToolDefinition(
    name="daily_append",
    description="Append content to today's daily note.",
    params_model=DailyAppendParams,
    execute=execute,
)
