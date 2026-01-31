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


class AskClarificationParams(BaseModel):
    """Parameters for asking clarifying questions."""

    ambiguous_term: str = Field(..., description="The user's term that matched multiple items")
    matches: list[str] = Field(..., description="List of matching note names")
    question: str = Field(..., description="Clarifying question to ask the user")


def get_tool_definitions() -> list[dict]:
    """Get OpenAI function definitions for all tools.

    All tools use strict mode for reliable schema adherence.
    Uses Responses API format (flat structure, not nested under 'function' key).
    See: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/responses

    Returns:
        List of tool definitions in Responses API format.
    """
    return [
        {
            "type": "function",
            "name": "search_notes",
            "description": "Search for notes in the vault by name. Use this to find existing notes before creating wikilinks or to check if a note already exists.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to find notes by name",
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "read_note",
            "description": "Read the full content of an existing note. Use this to check existing content before updating a note.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "note_name": {
                        "type": "string",
                        "description": "Name of the note to read (without .md extension)",
                    },
                },
                "required": ["note_name"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "upsert_note",
            "description": "Create a new note or replace an existing one. When updating, always read_note first, then provide the complete note content with your changes merged in. Always include proper YAML frontmatter with title, type, tags, created date, and related links.",
            "strict": True,
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
                        "type": ["string", "null"],
                        "description": "Target folder for new notes: Meetings, Centring, or Records. Use null to use default folder.",
                    },
                },
                "required": ["note_name", "content", "folder"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "ask_clarification",
            "description": "Ask the user to clarify an ambiguous reference BEFORE taking action. Use when search returns multiple matches.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "ambiguous_term": {
                        "type": "string",
                        "description": "User's original term",
                    },
                    "matches": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Matching notes",
                    },
                    "question": {
                        "type": "string",
                        "description": "Question to ask",
                    },
                },
                "required": ["ambiguous_term", "matches", "question"],
                "additionalProperties": False,
            },
        },
    ]
