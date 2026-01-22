"""Unit tests for orchestrator module."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent.orchestrator import Orchestrator, INVALID_CHARS


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = MagicMock()
    settings.obsidian_vault_path = Path("/vault")
    settings.obsidian_api_url = "https://127.0.0.1:27124"
    settings.obsidian_api_key = "test-key"
    settings.azure_openai_endpoint = "https://test.openai.azure.com"
    settings.azure_openai_api_key = "test-key"
    settings.azure_openai_deployment = "gpt-4o"
    settings.default_note_folder = "Inbox"
    settings.reasoning_effort = "medium"
    return settings


class TestInvalidCharsPattern:
    """Tests for INVALID_CHARS regex pattern."""

    def test_matches_forward_slash(self):
        """Test pattern matches forward slash."""
        assert INVALID_CHARS.search("/")

    def test_matches_backslash(self):
        """Test pattern matches backslash."""
        assert INVALID_CHARS.search("\\")

    def test_matches_colon(self):
        """Test pattern matches colon."""
        assert INVALID_CHARS.search(":")

    def test_matches_asterisk(self):
        """Test pattern matches asterisk."""
        assert INVALID_CHARS.search("*")

    def test_matches_question_mark(self):
        """Test pattern matches question mark."""
        assert INVALID_CHARS.search("?")

    def test_matches_quote(self):
        """Test pattern matches double quote."""
        assert INVALID_CHARS.search('"')

    def test_matches_angle_brackets(self):
        """Test pattern matches angle brackets."""
        assert INVALID_CHARS.search("<")
        assert INVALID_CHARS.search(">")

    def test_matches_pipe(self):
        """Test pattern matches pipe."""
        assert INVALID_CHARS.search("|")

    def test_does_not_match_normal_chars(self):
        """Test pattern does not match normal characters."""
        assert not INVALID_CHARS.search("abc123")
        assert not INVALID_CHARS.search("Hello World")
        assert not INVALID_CHARS.search("Note-Name_v2")


class TestOrchestratorSanitizeNoteName:
    """Tests for Orchestrator._sanitize_note_name method."""

    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator with mocked dependencies."""
        with patch("src.agent.orchestrator.VaultIndex"), \
             patch("src.agent.orchestrator.AsyncOpenAI"):
            return Orchestrator(mock_settings)

    def test_sanitize_replaces_slash(self, orchestrator):
        """Test that forward slash is replaced."""
        result = orchestrator._sanitize_note_name("foo/bar")
        assert "/" not in result
        assert result == "foo-bar"

    def test_sanitize_replaces_backslash(self, orchestrator):
        """Test that backslash is replaced."""
        result = orchestrator._sanitize_note_name("foo\\bar")
        assert "\\" not in result
        assert result == "foo-bar"

    def test_sanitize_replaces_colon(self, orchestrator):
        """Test that colon is replaced."""
        result = orchestrator._sanitize_note_name("Meeting: 2024")
        assert ":" not in result
        assert result == "Meeting- 2024"

    def test_sanitize_replaces_multiple_chars(self, orchestrator):
        """Test that multiple invalid chars are replaced."""
        result = orchestrator._sanitize_note_name("Test*File?Name")
        assert "*" not in result
        assert "?" not in result

    def test_sanitize_preserves_valid_chars(self, orchestrator):
        """Test that valid characters are preserved."""
        result = orchestrator._sanitize_note_name("Valid Note-Name_v2")
        assert result == "Valid Note-Name_v2"

    def test_sanitize_strips_whitespace(self, orchestrator):
        """Test that leading/trailing whitespace is stripped."""
        result = orchestrator._sanitize_note_name("  Note Name  ")
        assert result == "Note Name"


class TestOrchestratorProcessMessage:
    """Tests for Orchestrator.process_message method."""

    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator with mocked dependencies."""
        with patch("src.agent.orchestrator.VaultIndex") as MockVaultIndex, \
             patch("src.agent.orchestrator.AsyncOpenAI") as MockLLM:

            mock_vault_index = MagicMock()
            mock_vault_index.get_vault_summary.return_value = {
                "total_notes": 10,
                "folders": ["Meetings", "People"],
                "recent_notes": ["Note1", "Note2"],
            }
            mock_vault_index.get_hub_notes.return_value = ["MEETINGS", "RECORDS"]
            MockVaultIndex.return_value = mock_vault_index

            mock_llm = MagicMock()
            MockLLM.return_value = mock_llm

            orch = Orchestrator(mock_settings)
            orch._llm = mock_llm
            return orch

    @pytest.mark.asyncio
    async def test_process_message_checks_health(self, orchestrator):
        """Test that process_message checks Obsidian health."""
        with patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.health_check.return_value = False
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            result = await orchestrator.process_message("Hello")
            assert "Obsidian is not running" in result

    @pytest.mark.asyncio
    async def test_process_message_refreshes_index(self, orchestrator):
        """Test that process_message refreshes vault index."""
        with patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.health_check.return_value = True
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            # Mock Responses API response with no tool calls (just text output)
            mock_response = MagicMock()
            mock_response.output = []  # No function calls
            mock_response.output_text = "Response"
            orchestrator._llm.responses.create = AsyncMock(return_value=mock_response)

            await orchestrator.process_message("Hello")
            orchestrator._vault_index.refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_message_returns_response(self, orchestrator):
        """Test that process_message returns LLM response."""
        with patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.health_check.return_value = True
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            # Mock Responses API response
            mock_response = MagicMock()
            mock_response.output = []  # No function calls
            mock_response.output_text = "Created note successfully!"
            orchestrator._llm.responses.create = AsyncMock(return_value=mock_response)

            result = await orchestrator.process_message("Create a note")
            assert result == "Created note successfully!"


class TestOrchestratorToRelativePath:
    """Tests for Orchestrator._to_relative_path method."""

    @pytest.fixture
    def orchestrator_with_abs_path(self):
        """Create orchestrator with platform-appropriate absolute vault path."""
        import sys
        settings = MagicMock()
        # Use platform-appropriate absolute path
        if sys.platform == "win32":
            settings.obsidian_vault_path = Path("C:/vault")
        else:
            settings.obsidian_vault_path = Path("/vault")
        settings.obsidian_api_url = "https://127.0.0.1:27124"
        settings.obsidian_api_key = "test-key"
        settings.azure_openai_endpoint = "https://test.openai.azure.com"
        settings.azure_openai_api_key = "test-key"
        settings.azure_openai_deployment = "gpt-4o"
        settings.default_note_folder = "Inbox"
        settings.reasoning_effort = "medium"

        with patch("src.agent.orchestrator.VaultIndex"), \
             patch("src.agent.orchestrator.AsyncOpenAI"):
            return Orchestrator(settings)

    def test_converts_absolute_to_relative(self, orchestrator_with_abs_path):
        """Absolute path is converted to relative."""
        vault_path = orchestrator_with_abs_path._settings.obsidian_vault_path
        abs_path = vault_path / "Meetings" / "Note.md"
        result = orchestrator_with_abs_path._to_relative_path(abs_path)
        assert result == Path("Meetings/Note.md")

    def test_preserves_relative_path(self, orchestrator_with_abs_path):
        """Relative path is returned unchanged."""
        rel_path = Path("Meetings/Note.md")
        result = orchestrator_with_abs_path._to_relative_path(rel_path)
        assert result == Path("Meetings/Note.md")


class TestOrchestratorCheckHealth:
    """Tests for Orchestrator.check_health method."""

    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator with mocked dependencies."""
        with patch("src.agent.orchestrator.VaultIndex"), \
             patch("src.agent.orchestrator.AsyncOpenAI"):
            return Orchestrator(mock_settings)

    @pytest.mark.asyncio
    async def test_check_health_returns_true_when_healthy(self, orchestrator):
        """Test check_health returns (True, None) when API is available."""
        with patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.health_check.return_value = True
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            is_healthy, error = await orchestrator.check_health()
            assert is_healthy is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_health_returns_false_when_unhealthy(self, orchestrator):
        """Test check_health returns (False, message) when API unavailable."""
        with patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.health_check.return_value = False
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            is_healthy, error = await orchestrator.check_health()
            assert is_healthy is False
            assert "not available" in error


class TestOrchestratorMaxIterations:
    """Tests for max iterations handling."""

    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator with mocked dependencies."""
        with patch("src.agent.orchestrator.VaultIndex") as MockVaultIndex, \
             patch("src.agent.orchestrator.AsyncOpenAI") as MockLLM:

            mock_vault_index = MagicMock()
            mock_vault_index.get_vault_summary.return_value = {
                "total_notes": 10,
                "folders": ["Meetings", "People"],
                "recent_notes": ["Note1", "Note2"],
            }
            mock_vault_index.get_hub_notes.return_value = ["MEETINGS", "RECORDS"]
            MockVaultIndex.return_value = mock_vault_index

            mock_llm = MagicMock()
            MockLLM.return_value = mock_llm

            orch = Orchestrator(mock_settings)
            orch._llm = mock_llm
            return orch

    @pytest.mark.asyncio
    async def test_max_iterations_injects_summary_message(self, orchestrator):
        """Test that max iterations injects a user message before final LLM call."""
        import json
        from src.agent.orchestrator import MAX_TOOL_ITERATIONS

        with patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.health_check.return_value = True
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            # Create a tool call response for Responses API format
            def create_tool_call_response():
                mock_response = MagicMock()
                mock_tool_call = MagicMock()
                mock_tool_call.type = "function_call"
                mock_tool_call.call_id = "call_123"
                mock_tool_call.name = "search_notes"
                mock_tool_call.arguments = json.dumps({"query": "test"})
                mock_tool_call.model_dump.return_value = {
                    "type": "function_call",
                    "call_id": "call_123",
                    "name": "search_notes",
                    "arguments": '{"query": "test"}'
                }
                mock_response.output = [mock_tool_call]
                mock_response.output_text = None
                return mock_response

            # Create final response (no tools)
            final_response = MagicMock()
            final_response.output = []
            final_response.output_text = "Summary of what was done"

            # Return tool call responses for MAX_TOOL_ITERATIONS, then final
            call_count = [0]
            def mock_create(**kwargs):
                call_count[0] += 1
                if call_count[0] <= MAX_TOOL_ITERATIONS:
                    return create_tool_call_response()
                return final_response

            orchestrator._llm.responses.create = AsyncMock(side_effect=mock_create)
            orchestrator._vault_index.search_notes.return_value = []

            result = await orchestrator.process_message("Test message")

            # Verify final call was made without tools
            final_call = orchestrator._llm.responses.create.call_args_list[-1]
            assert final_call.kwargs.get("tools") is None

            # Verify the injected user message was in the input
            input_items = final_call.kwargs.get("input", [])
            last_user_message = None
            for item in reversed(input_items):
                if item.get("role") == "user":
                    last_user_message = item
                    break

            assert last_user_message is not None
            assert "run out of tool calls" in last_user_message["content"]
            assert "Summarize" in last_user_message["content"]
