"""Tool for deleting a note with explicit confirmation."""

from __future__ import annotations

from pydantic import Field

from src.adapters.base import AgentResponse, ButtonOption, PendingAction
from src.tools._shared import PathToolModel, ensure_markdown_path
from src.tools.base import ToolContext, ToolDefinition, ToolResult


class DeleteNoteParams(PathToolModel):
    """Parameters for note deletion."""

    confirmed: bool = Field(
        default=False,
        description="Set to true only after the user has explicitly confirmed deletion.",
    )


async def execute(params: DeleteNoteParams, ctx: ToolContext) -> ToolResult:
    note_path = ensure_markdown_path(params.path)
    if not params.confirmed:
        prompt = f"Delete '{note_path}'?"
        response = AgentResponse(
            text=prompt,
            action=PendingAction(
                kind="confirm_delete",
                prompt=prompt,
                options=[
                    ButtonOption(label="Delete", value=f"delete:{note_path}", style="danger"),
                    ButtonOption(label="Cancel", value=f"cancel:{note_path}"),
                ],
                metadata={"path": note_path},
            ),
        )
        return ToolResult(content=prompt, stop=True, response=response)

    deleted = await ctx.rest.delete_note(note_path)
    if deleted:
        return ToolResult(content=f"Deleted '{note_path}'.")
    return ToolResult(content=f"Note '{note_path}' was already absent.")


tool = ToolDefinition(
    name="delete_note",
    description="Delete a note. Requires explicit user confirmation before execution.",
    params_model=DeleteNoteParams,
    execute=execute,
)
