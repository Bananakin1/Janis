"""Unit tests for agent tools module."""

import pytest
from pydantic import ValidationError

from src.agent.tools import (
    SearchNotesParams,
    ReadNoteParams,
    UpsertNoteParams,
    AskClarificationParams,
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

    def test_valid_params_with_prepend_true(self):
        """Test valid params with prepend=True."""
        params = UpsertNoteParams(
            note_name="Curinos",
            content="## 02/20/2026\n**With:** Olly\nDiscussed Q1.",
            folder="Meetings",
            prepend=True,
        )
        assert params.prepend is True

    def test_valid_params_with_prepend_null(self):
        """Test valid params with prepend=None (explicit)."""
        params = UpsertNoteParams(
            note_name="Curinos",
            content="Full content here",
            folder="Meetings",
            prepend=None,
        )
        assert params.prepend is None

    def test_valid_params_without_prepend(self):
        """Test that prepend defaults to None when omitted."""
        params = UpsertNoteParams(
            note_name="Test Note",
            content="Content",
        )
        assert params.prepend is None

    def test_missing_required_raises(self):
        """Test that missing required fields raises error."""
        with pytest.raises(ValidationError):
            UpsertNoteParams(note_name="Test")

        with pytest.raises(ValidationError):
            UpsertNoteParams(content="Content")


class TestAskClarificationParams:
    """Tests for AskClarificationParams model."""

    def test_valid_params(self):
        """Test valid clarification params."""
        params = AskClarificationParams(
            ambiguous_term="Sarah",
            matches=["Sarah Chen", "Sarah Miller"],
            question="Which Sarah did you mean?",
        )
        assert params.ambiguous_term == "Sarah"
        assert params.matches == ["Sarah Chen", "Sarah Miller"]
        assert params.question == "Which Sarah did you mean?"

    def test_missing_required_raises(self):
        """Test that missing required fields raises error."""
        with pytest.raises(ValidationError):
            AskClarificationParams(ambiguous_term="Sarah")

        with pytest.raises(ValidationError):
            AskClarificationParams(
                ambiguous_term="Sarah",
                matches=["Sarah Chen"],
            )


class TestGetToolDefinitions:
    """Tests for get_tool_definitions function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        definitions = get_tool_definitions()
        assert isinstance(definitions, list)

    def test_has_four_tools(self):
        """Test that there are exactly 4 tools defined."""
        definitions = get_tool_definitions()
        assert len(definitions) == 4

    def test_tool_structure(self):
        """Test that each tool has correct Responses API structure (flat, not nested)."""
        definitions = get_tool_definitions()

        for tool in definitions:
            assert "type" in tool
            assert tool["type"] == "function"
            # Responses API uses flat structure - name/description at top level
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            # Should NOT have nested "function" key (that's Chat Completions format)
            assert "function" not in tool

    def test_tool_names(self):
        """Test that all expected tools are defined."""
        definitions = get_tool_definitions()
        names = {tool["name"] for tool in definitions}

        assert names == {"search_notes", "read_note", "upsert_note", "ask_clarification"}

    def test_search_notes_schema(self):
        """Test search_notes tool schema."""
        definitions = get_tool_definitions()
        search_tool = next(t for t in definitions if t["name"] == "search_notes")

        params = search_tool["parameters"]
        assert params["type"] == "object"
        assert "query" in params["properties"]
        assert "query" in params["required"]

    def test_upsert_note_schema(self):
        """Test upsert_note tool schema."""
        definitions = get_tool_definitions()
        upsert_tool = next(t for t in definitions if t["name"] == "upsert_note")

        params = upsert_tool["parameters"]
        assert "note_name" in params["properties"]
        assert "content" in params["properties"]
        assert "folder" in params["properties"]
        assert "note_name" in params["required"]
        assert "content" in params["required"]
        # folder is required but nullable (strict mode requires all fields in required)
        assert "folder" in params["required"]
        assert params["properties"]["folder"]["type"] == ["string", "null"]
        # Verify strict mode settings
        assert upsert_tool.get("strict") is True
        assert params.get("additionalProperties") is False

    def test_upsert_note_has_prepend_property(self):
        """Test that upsert_note schema includes prepend in properties and required."""
        definitions = get_tool_definitions()
        upsert_tool = next(t for t in definitions if t["name"] == "upsert_note")

        params = upsert_tool["parameters"]
        assert "prepend" in params["properties"]
        assert params["properties"]["prepend"]["type"] == ["boolean", "null"]
        assert "prepend" in params["required"]

    def test_ask_clarification_schema(self):
        """Test ask_clarification tool schema."""
        definitions = get_tool_definitions()
        clarify_tool = next(t for t in definitions if t["name"] == "ask_clarification")

        params = clarify_tool["parameters"]
        assert "ambiguous_term" in params["properties"]
        assert "matches" in params["properties"]
        assert "question" in params["properties"]
        assert params["properties"]["matches"]["type"] == "array"
        assert "ambiguous_term" in params["required"]
        assert "matches" in params["required"]
        assert "question" in params["required"]
