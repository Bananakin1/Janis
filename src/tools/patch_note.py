"""Tool for section-level note patching."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from src.tools._shared import PathToolModel, ensure_markdown_path
from src.tools.base import ToolContext, ToolDefinition, ToolResult

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def _extract_headings(markdown: str) -> list[str]:
    """Return all heading texts found in markdown content."""
    return [m.group(2).strip() for m in _HEADING_RE.finditer(markdown)]


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


async def execute(params: PatchNoteParams, ctx: ToolContext) -> ToolResult | str:
    note_path = ensure_markdown_path(params.path)

    # Pre-flight: read the note and validate the target exists
    if params.target_type == "heading":
        note_content = await ctx.rest.read_note(note_path)
        if note_content is None:
            return ToolResult(
                content=f"Patch failed: '{note_path}' does not exist."
            )
        headings = _extract_headings(note_content)
        if params.target not in headings:
            heading_list = "\n".join(f"  - {h}" for h in headings) if headings else "  (no headings found)"
            return ToolResult(
                content=(
                    f"Patch failed: heading '{params.target}' not found in '{note_path}'.\n"
                    f"Available headings:\n{heading_list}\n"
                    "Retry with an exact heading from the list above, or use update_note instead."
                )
            )

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
