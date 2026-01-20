"""Pydantic models and OpenAI function definitions for agent tools."""

from typing import Optional

from pydantic import BaseModel, Field


class SearchNotesParams(BaseModel):
    """Parameters for searching notes by name."""

    query: str = Field(..., description="Search query to find notes by name")


class ReadNoteParams(BaseModel):
    """Parameters for reading a note's content."""

    note_name: str = Field(..., description="Name of the note to read (without .md extension)")


class UpsertNoteParams(BaseModel):
    """Parameters for creating or updating a note."""

    note_name: str = Field(..., description="Name of the note (without .md extension)")
    content: str = Field(..., description="Markdown content for the note")
    folder: Optional[str] = Field(
        default=None,
        description="Target folder for the note (e.g., 'Meetings', 'People')",
    )


def get_tool_definitions() -> list[dict]:
    """Get OpenAI function definitions for all tools.

    Returns:
        List of tool definitions in OpenAI format.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "search_notes",
                "description": "Search for notes in the vault by name. Use this to find existing notes before creating wikilinks or to check if a note already exists.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query to find notes by name",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_note",
                "description": "Read the full content of an existing note. Use this to check existing content before updating a note.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note_name": {
                            "type": "string",
                            "description": "Name of the note to read (without .md extension)",
                        },
                    },
                    "required": ["note_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "upsert_note",
                "description": "Create a new note or update an existing one. When updating, new content is appended. Always include proper YAML frontmatter with title, type, tags, created date, and related links.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note_name": {
                            "type": "string",
                            "description": "Name of the note (without .md extension)",
                        },
                        "content": {
                            "type": "string",
                            "description": "Full markdown content including frontmatter",
                        },
                        "folder": {
                            "type": "string",
                            "description": "Target folder: Meetings, People, Projects, Topics, or Inbox",
                        },
                    },
                    "required": ["note_name", "content"],
                },
            },
        },
    ]
