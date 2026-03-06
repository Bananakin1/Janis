"""Backward-compatible exports for legacy tool imports."""

from src.tools.ask_clarification import AskClarificationParams
from src.tools.read_note import ReadNoteParams
from src.tools.search_notes import SearchNotesParams
from src.tools.upsert_note import UpsertNoteParams
from src.tools.registry import ToolRegistry


def get_tool_definitions() -> list[dict]:
    """Return discovered tool schemas for legacy callers."""
    return ToolRegistry.discover().get_schemas()


__all__ = [
    "AskClarificationParams",
    "ReadNoteParams",
    "SearchNotesParams",
    "UpsertNoteParams",
    "get_tool_definitions",
]
