"""Unit tests for agent tools module."""

import pytest
from pydantic import ValidationError

from src.agent.tools import (
    SearchNotesParams,
    ReadNoteParams,
    UpsertNoteParams,
    get_tool_definitions,
)


class TestSearchNotesParams:
    """Tests for SearchNotesParams model."""

    def test_valid_query(self):
        """Test valid search query."""
        params = SearchNotesParams(query="meeting notes")
        assert params.query == "meeting notes"

    def test_empty_query_allowed(self):
        """Test that empty string is allowed."""
        params = SearchNotesParams(query="")
        assert params.query == ""

    def test_missing_query_raises(self):
        """Test that missing query raises validation error."""
        with pytest.raises(ValidationError):
            SearchNotesParams()


class TestReadNoteParams:
    """Tests for ReadNoteParams model."""

    def test_valid_note_name(self):
        """Test valid note name."""
        params = ReadNoteParams(note_name="My Note")
        assert params.note_name == "My Note"

    def test_missing_note_name_raises(self):
        """Test that missing note_name raises validation error."""
        with pytest.raises(ValidationError):
            ReadNoteParams()


class TestUpsertNoteParams:
    """Tests for UpsertNoteParams model."""

    def test_valid_params_with_folder(self):
        """Test valid params with folder."""
        params = UpsertNoteParams(
            note_name="Test Note",
            content="# Test\n\nContent here.",
            folder="Meetings",
        )
        assert params.note_name == "Test Note"
        assert params.content == "# Test\n\nContent here."
        assert params.folder == "Meetings"

    def test_valid_params_without_folder(self):
        """Test valid params without folder (optional)."""
        params = UpsertNoteParams(
            note_name="Test Note",
            content="Content",
        )
        assert params.note_name == "Test Note"
        assert params.folder is None

    def test_missing_required_raises(self):
        """Test that missing required fields raises error."""
        with pytest.raises(ValidationError):
            UpsertNoteParams(note_name="Test")

        with pytest.raises(ValidationError):
            UpsertNoteParams(content="Content")


class TestGetToolDefinitions:
    """Tests for get_tool_definitions function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        definitions = get_tool_definitions()
        assert isinstance(definitions, list)

    def test_has_three_tools(self):
        """Test that there are exactly 3 tools defined."""
        definitions = get_tool_definitions()
        assert len(definitions) == 3

    def test_tool_structure(self):
        """Test that each tool has correct structure."""
        definitions = get_tool_definitions()

        for tool in definitions:
            assert "type" in tool
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_tool_names(self):
        """Test that all expected tools are defined."""
        definitions = get_tool_definitions()
        names = {tool["function"]["name"] for tool in definitions}

        assert names == {"search_notes", "read_note", "upsert_note"}

    def test_search_notes_schema(self):
        """Test search_notes tool schema."""
        definitions = get_tool_definitions()
        search_tool = next(
            t for t in definitions if t["function"]["name"] == "search_notes"
        )

        params = search_tool["function"]["parameters"]
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "query" in params["required"]

    def test_upsert_note_schema(self):
        """Test upsert_note tool schema."""
        definitions = get_tool_definitions()
        upsert_tool = next(
            t for t in definitions if t["function"]["name"] == "upsert_note"
        )

        params = upsert_tool["function"]["parameters"]
        assert "note_name" in params["properties"]
        assert "content" in params["properties"]
        assert "folder" in params["properties"]
        assert "note_name" in params["required"]
        assert "content" in params["required"]
        # folder is optional
        assert "folder" not in params.get("required", [])
