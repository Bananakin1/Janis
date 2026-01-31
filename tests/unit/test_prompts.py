"""Unit tests for prompts module."""

import pytest
from datetime import datetime

from src.agent.prompts import build_system_prompt, SYSTEM_PROMPT_TEMPLATE


class TestSystemPromptTemplate:
    """Tests for SYSTEM_PROMPT_TEMPLATE."""

    def test_template_has_environment_placeholders(self):
        """Test template contains environment placeholders."""
        assert "{today}" in SYSTEM_PROMPT_TEMPLATE
        assert "{total_notes}" in SYSTEM_PROMPT_TEMPLATE
        assert "{folders}" in SYSTEM_PROMPT_TEMPLATE
        assert "{recent_notes}" in SYSTEM_PROMPT_TEMPLATE

    def test_template_has_structured_blocks(self):
        """Test template includes GPT-5.2 structured blocks."""
        assert "<environment>" in SYSTEM_PROMPT_TEMPLATE
        assert "</environment>" in SYSTEM_PROMPT_TEMPLATE
        assert "<design_and_scope_constraints>" in SYSTEM_PROMPT_TEMPLATE
        assert "</design_and_scope_constraints>" in SYSTEM_PROMPT_TEMPLATE
        assert "<uncertainty_and_ambiguity>" in SYSTEM_PROMPT_TEMPLATE
        assert "</uncertainty_and_ambiguity>" in SYSTEM_PROMPT_TEMPLATE
        assert "<note_format>" in SYSTEM_PROMPT_TEMPLATE
        assert "</note_format>" in SYSTEM_PROMPT_TEMPLATE
        assert "<output_format>" in SYSTEM_PROMPT_TEMPLATE
        assert "</output_format>" in SYSTEM_PROMPT_TEMPLATE

    def test_template_describes_tools(self):
        """Test template includes tool descriptions."""
        assert "search_notes" in SYSTEM_PROMPT_TEMPLATE
        assert "ask_clarification" in SYSTEM_PROMPT_TEMPLATE

    def test_template_includes_folder_structure(self):
        """Test template includes folder structure information."""
        assert "Meetings/" in SYSTEM_PROMPT_TEMPLATE
        assert "Centring/" in SYSTEM_PROMPT_TEMPLATE
        assert "Records/" in SYSTEM_PROMPT_TEMPLATE

    def test_template_includes_frontmatter_example(self):
        """Test template includes frontmatter example."""
        assert "title:" in SYSTEM_PROMPT_TEMPLATE
        assert "type:" in SYSTEM_PROMPT_TEMPLATE
        assert "tags:" in SYSTEM_PROMPT_TEMPLATE


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_returns_string(self):
        """Test that function returns a string."""
        result = build_system_prompt({})
        assert isinstance(result, str)

    def test_includes_total_notes(self):
        """Test that total notes count is included."""
        result = build_system_prompt({"total_notes": 42})
        assert "42 notes" in result

    def test_includes_folders(self):
        """Test that folders are included."""
        result = build_system_prompt({
            "folders": ["Meetings", "People", "Projects"]
        })
        assert "Meetings" in result
        assert "People" in result
        assert "Projects" in result

    def test_includes_recent_notes(self):
        """Test that recent notes are included."""
        result = build_system_prompt({
            "recent_notes": ["Note A", "Note B", "Note C"]
        })
        assert "Note A" in result
        assert "Note B" in result
        assert "Note C" in result

    def test_includes_today_date(self):
        """Test that today's date is included."""
        today = datetime.now().strftime("%m/%d/%Y")
        result = build_system_prompt({})
        assert today in result

    def test_handles_empty_summary(self):
        """Test that empty summary is handled gracefully."""
        result = build_system_prompt({})
        assert "0 notes" in result

    def test_handles_empty_folders(self):
        """Test that empty folders list is handled."""
        result = build_system_prompt({"folders": []})
        assert "folders: None" in result

    def test_handles_empty_recent_notes(self):
        """Test that empty recent notes is handled."""
        result = build_system_prompt({"recent_notes": []})
        assert "Recent: None" in result

    def test_limits_recent_notes_display(self):
        """Test that recent notes are limited."""
        many_notes = [f"Note {i}" for i in range(20)]
        result = build_system_prompt({"recent_notes": many_notes})
        # Should only show first 5
        assert "Note 0" in result
        assert "Note 4" in result

    def test_no_placeholders_remaining(self):
        """Test that no unresolved placeholders remain."""
        result = build_system_prompt({
            "total_notes": 10,
            "folders": ["Test"],
            "recent_notes": ["Note"],
        })
        assert "{today}" not in result
        assert "{total_notes}" not in result
        assert "{folders}" not in result
        assert "{recent_notes}" not in result
