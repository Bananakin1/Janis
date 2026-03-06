"""Tool for reading today's daily note."""

from __future__ import annotations

from src.tools._shared import ToolModel
from src.tools.base import ToolContext, ToolDefinition


class DailyReadParams(ToolModel):
    """No-argument model for daily note reads."""


async def execute(params: DailyReadParams, ctx: ToolContext) -> str:
    content = await ctx.rest.read_daily()
    if content is None:
        return "Today's daily note was not found."
    return content


tool = ToolDefinition(
    name="daily_read",
    description="Read today's daily note via the periodic notes endpoint.",
    params_model=DailyReadParams,
    execute=execute,
)
