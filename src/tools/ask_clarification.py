"""Tool for disambiguation prompts."""

from __future__ import annotations

from pydantic import Field

from src.adapters.base import AgentResponse, ButtonOption, PendingAction
from src.tools._shared import ToolModel
from src.tools.base import ToolContext, ToolDefinition, ToolResult


class AskClarificationParams(ToolModel):
    """Parameters for clarification requests."""

    ambiguous_term: str = Field(..., description="The user term that needs clarification.")
    matches: list[str] = Field(
        ...,
        min_length=1,
        description="Candidate note names to present to the user.",
    )
    question: str = Field(..., description="Clarifying question to ask the user.")


async def execute(params: AskClarificationParams, ctx: ToolContext) -> ToolResult:
    prompt = params.question.strip()
    response = AgentResponse(
        text=prompt,
        action=PendingAction(
            kind="choose_note",
            prompt=prompt,
            options=[ButtonOption(label=match[:80], value=match) for match in params.matches[:5]],
            metadata={"ambiguous_term": params.ambiguous_term, "matches": params.matches},
        ),
    )
    return ToolResult(content=prompt, stop=True, response=response)


tool = ToolDefinition(
    name="ask_clarification",
    description="Ask the user to choose between multiple matching notes before taking action.",
    params_model=AskClarificationParams,
    execute=execute,
)
