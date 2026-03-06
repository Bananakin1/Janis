"""Tool for section-level note patching."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from src.tools._shared import PathToolModel, ensure_markdown_path
from src.tools.base import ToolContext, ToolDefinition


class PatchNoteParams(PathToolModel):
    """Parameters for note patching."""

    content: str = Field(..., description="Content to apply to the target section.")
    target_type: Literal["heading", "block", "frontmatter"] = Field(
        ...,
        description="Type of target: 'heading', 'block', or 'frontmatter'.",
    )
    target: str = Field(
        ...,
        description="The heading text, block reference, or frontmatter key to target.",
    )
    operation: Literal["append", "prepend", "replace"] = Field(
        default="replace",
        description="How to apply the content: 'append', 'prepend', or 'replace'.",
    )


async def execute(params: PatchNoteParams, ctx: ToolContext) -> str:
    note_path = ensure_markdown_path(params.path)
    await ctx.rest.patch_note(
        note_path,
        params.content,
        target=params.target,
        target_type=params.target_type,
        operation=params.operation,
    )
    return f"Patched '{note_path}' ({params.target_type}: {params.target})."


tool = ToolDefinition(
    name="patch_note",
    description="Patch a specific section of a note by heading, block reference, or frontmatter key.",
    params_model=PatchNoteParams,
    execute=execute,
)
