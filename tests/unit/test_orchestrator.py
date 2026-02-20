"""Unit tests for orchestrator module."""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent.orchestrator import Orchestrator, ConversationTurn, INVALID_CHARS, DATE_HEADING_RE


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


class TestOrchestratorConversationHistory:
    """Tests for conversation history (working memory)."""

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

    def _setup_simple_response(self, orchestrator, response_text="Done"):
        """Configure orchestrator to return a simple text response."""
        with patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.health_check.return_value = True
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            mock_response = MagicMock()
            mock_response.output = []
            mock_response.output_text = response_text
            orchestrator._llm.responses.create = AsyncMock(return_value=mock_response)

            return MockClient

    @pytest.mark.asyncio
    async def test_history_populated_after_call(self, orchestrator):
        """Test that history contains user and assistant turns after a call."""
        with self._setup_simple_response(orchestrator, "Response text"):
            await orchestrator.process_message("Hello", author="Alice")

        assert len(orchestrator._history) == 2
        assert orchestrator._history[0] == ConversationTurn("user", "Alice", "Hello")
        assert orchestrator._history[1] == ConversationTurn("assistant", "Janis", "Response text")

    @pytest.mark.asyncio
    async def test_history_injected_into_llm_input(self, orchestrator):
        """Test that history entries appear in LLM input on second call."""
        # First call
        with self._setup_simple_response(orchestrator, "First response"):
            await orchestrator.process_message("First message", author="Alice")

        # Second call
        with self._setup_simple_response(orchestrator, "Second response"):
            await orchestrator.process_message("Second message", author="Bob")

        # Check the input_items from the second LLM call
        call_args = orchestrator._llm.responses.create.call_args
        input_items = call_args.kwargs.get("input", [])

        # Should have: system, history user, history assistant, current user
        assert input_items[0]["role"] == "system"
        assert input_items[1] == {"role": "user", "content": "[Alice]: First message"}
        assert input_items[2] == {"role": "assistant", "content": "First response"}
        assert input_items[3] == {"role": "user", "content": "[Bob]: Second message"}

    @pytest.mark.asyncio
    async def test_author_attribution_format(self, orchestrator):
        """Test that current message uses [Author]: format."""
        with self._setup_simple_response(orchestrator, "OK"):
            await orchestrator.process_message("Test msg", author="Charlie")

        call_args = orchestrator._llm.responses.create.call_args
        input_items = call_args.kwargs.get("input", [])

        user_msg = input_items[-1]
        assert user_msg["content"] == "[Charlie]: Test msg"

    @pytest.mark.asyncio
    async def test_history_default_author(self, orchestrator):
        """Test that default author is 'User'."""
        with self._setup_simple_response(orchestrator, "OK"):
            await orchestrator.process_message("Hello")

        assert orchestrator._history[0].author == "User"

    @pytest.mark.asyncio
    async def test_history_maxlen(self, orchestrator):
        """Test that history is bounded to 4 entries (2 turns)."""
        for i in range(3):
            with self._setup_simple_response(orchestrator, f"Response {i}"):
                await orchestrator.process_message(f"Message {i}", author="User")

        # maxlen=4 means only last 2 turns (4 entries) are kept
        assert len(orchestrator._history) == 4
        assert orchestrator._history[0] == ConversationTurn("user", "User", "Message 1")
        assert orchestrator._history[1] == ConversationTurn("assistant", "Janis", "Response 1")


class TestOrchestratorPrependToNote:
    """Tests for Orchestrator._prepend_to_note static method."""

    def test_prepend_inserts_before_first_date_heading(self):
        """New content is inserted before the first date heading."""
        existing = (
            "---\ntitle: Curinos\n---\n\n"
            "## People\n| Name | Role | Notes |\n|---|---|---|\n| Olly | PM | |\n\n"
            "## 01/13/2026\n**With:** Olly\nOld meeting notes\n"
        )
        new = "## 02/20/2026\n**With:** Olly\nNew meeting notes"

        result = Orchestrator._prepend_to_note(existing, new)

        idx_new = result.index("## 02/20/2026")
        idx_old = result.index("## 01/13/2026")
        assert idx_new < idx_old

    def test_prepend_preserves_frontmatter(self):
        """Frontmatter stays at the top of the note."""
        existing = "---\ntitle: Test\n---\n\n## 12/01/2025\nOld notes\n"
        new = "## 01/15/2026\nNew notes"

        result = Orchestrator._prepend_to_note(existing, new)

        assert result.startswith("---\ntitle: Test\n---")
        assert result.index("---") < result.index("## 01/15/2026")

    def test_prepend_preserves_people_table(self):
        """People table stays between frontmatter and date sections."""
        existing = (
            "---\ntitle: ITK\n---\n\n"
            "## People\n| Name | Role | Notes |\n|---|---|---|\n| Joe | CTO | |\n\n"
            "## 12/09/2025\n**With:** Joe\nFirst meeting\n"
        )
        new = "## 02/20/2026\n**With:** Joe\nSecond meeting"

        result = Orchestrator._prepend_to_note(existing, new)

        idx_people = result.index("## People")
        idx_new = result.index("## 02/20/2026")
        idx_old = result.index("## 12/09/2025")
        assert idx_people < idx_new < idx_old

    def test_prepend_no_existing_dates_appends(self):
        """When no date headings exist, content is appended at the end."""
        existing = "---\ntitle: New Co\n---\n\n## People\n| Name | Role | Notes |\n"
        new = "## 02/20/2026\n**With:** Alice\nFirst meeting"

        result = Orchestrator._prepend_to_note(existing, new)

        assert "## 02/20/2026" in result
        assert result.index("## People") < result.index("## 02/20/2026")

    def test_prepend_individual_note_no_people_table(self):
        """Works correctly for individual notes without a People section."""
        existing = "---\ntitle: Reed Yamaguchi\n---\n\n## 01/10/2026\nOld notes\n"
        new = "## 02/20/2026\nNew notes"

        result = Orchestrator._prepend_to_note(existing, new)

        idx_new = result.index("## 02/20/2026")
        idx_old = result.index("## 01/10/2026")
        assert idx_new < idx_old
        assert result.startswith("---\ntitle: Reed")

    def test_prepend_whitespace_normalization(self):
        """No triple blank lines appear in the output."""
        existing = (
            "---\ntitle: Test\n---\n\n\n\n"
            "## 01/01/2026\nNotes\n"
        )
        new = "## 02/01/2026\nNew notes"

        result = Orchestrator._prepend_to_note(existing, new)

        assert "\n\n\n" not in result

    def test_prepend_multiple_existing_dates(self):
        """New date is inserted before all existing dates, preserving their order."""
        existing = (
            "---\ntitle: Multi\n---\n\n"
            "## 01/15/2026\nMeeting B\n\n"
            "## 12/01/2025\nMeeting A\n"
        )
        new = "## 02/20/2026\nMeeting C"

        result = Orchestrator._prepend_to_note(existing, new)

        idx_c = result.index("## 02/20/2026")
        idx_b = result.index("## 01/15/2026")
        idx_a = result.index("## 12/01/2025")
        assert idx_c < idx_b < idx_a


class TestOrchestratorExecuteToolSearch:
    """Tests for _execute_tool search via REST API."""

    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator with mocked dependencies."""
        with patch("src.agent.orchestrator.VaultIndex") as MockVaultIndex, \
             patch("src.agent.orchestrator.AsyncOpenAI"):
            mock_vault_index = MagicMock()
            MockVaultIndex.return_value = mock_vault_index
            orch = Orchestrator(mock_settings)
            return orch

    @pytest.mark.asyncio
    async def test_search_returns_formatted_results(self, orchestrator):
        """REST search results are formatted with filenames and context."""
        rest_client = AsyncMock()
        rest_client.search.return_value = [
            {"filename": "Meetings/Curinos.md", "matches": [{"match": "Q1 targets", "context": "Discussed Q1 targets with the team"}]},
            {"filename": "Centring/Roadmap.md", "matches": [{"match": "Q1 targets", "context": "Q1 targets include launch"}]},
        ]

        result = await orchestrator._execute_tool("search_notes", {"query": "Q1 targets"}, rest_client)

        rest_client.search.assert_called_once_with("Q1 targets", context_length=100)
        assert "Found 2 result(s):" in result
        assert '- Meetings/Curinos.md: "Discussed Q1 targets with the team"' in result
        assert '- Centring/Roadmap.md: "Q1 targets include launch"' in result

    @pytest.mark.asyncio
    async def test_search_no_results(self, orchestrator):
        """Empty search returns 'No matching notes found.'"""
        rest_client = AsyncMock()
        rest_client.search.return_value = []

        result = await orchestrator._execute_tool("search_notes", {"query": "nonexistent"}, rest_client)

        assert result == "No matching notes found."

    @pytest.mark.asyncio
    async def test_search_caps_at_20_results(self, orchestrator):
        """Only first 20 results are shown even if more are returned."""
        rest_client = AsyncMock()
        rest_client.search.return_value = [
            {"filename": f"Notes/Note{i}.md", "matches": [{"match": "test", "context": f"context {i}"}]}
            for i in range(25)
        ]

        result = await orchestrator._execute_tool("search_notes", {"query": "test"}, rest_client)

        assert "Found 25 result(s):" in result
        # Count displayed lines (each starts with "- ")
        lines = [line for line in result.split("\n") if line.startswith("- ")]
        assert len(lines) == 20

    @pytest.mark.asyncio
    async def test_search_result_without_matches(self, orchestrator):
        """Result with no context snippets shows filename only."""
        rest_client = AsyncMock()
        rest_client.search.return_value = [
            {"filename": "Inbox/Quick Note.md", "matches": []},
        ]

        result = await orchestrator._execute_tool("search_notes", {"query": "quick"}, rest_client)

        assert "Found 1 result(s):" in result
        assert "- Inbox/Quick Note.md" in result
        assert '"' not in result.split("- Inbox/Quick Note.md")[1].split("\n")[0]


class TestOrchestratorExecuteToolUpsertPrepend:
    """Tests for _execute_tool upsert with prepend flag."""

    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator with mocked dependencies."""
        with patch("src.agent.orchestrator.VaultIndex") as MockVaultIndex, \
             patch("src.agent.orchestrator.AsyncOpenAI"):
            mock_vault_index = MagicMock()
            MockVaultIndex.return_value = mock_vault_index
            orch = Orchestrator(mock_settings)
            return orch

    @pytest.mark.asyncio
    async def test_prepend_reads_existing_before_write(self, orchestrator):
        """Prepend mode reads the note, merges, then writes back."""
        # Note exists at Meetings/Curinos.md
        orchestrator._vault_index.get_note_path.return_value = Path("Meetings/Curinos.md")

        rest_client = AsyncMock()
        rest_client.read_note.return_value = (
            "---\ntitle: Curinos\n---\n\n## 01/13/2026\n**With:** Olly\nOld notes\n"
        )

        result = await orchestrator._execute_tool(
            "upsert_note",
            {
                "note_name": "Curinos",
                "content": "## 02/20/2026\n**With:** Olly\nNew notes",
                "folder": "Meetings",
                "prepend": True,
            },
            rest_client,
        )

        # Should have read the existing note
        rest_client.read_note.assert_called_once_with("Meetings/Curinos.md")
        # Should have written merged content
        rest_client.upsert_note.assert_called_once()
        written_content = rest_client.upsert_note.call_args[0][1]
        assert "## 02/20/2026" in written_content
        assert "## 01/13/2026" in written_content
        assert written_content.index("## 02/20/2026") < written_content.index("## 01/13/2026")
        assert "Prepended" in result

    @pytest.mark.asyncio
    async def test_prepend_false_uses_existing_behavior(self, orchestrator):
        """prepend=null follows the full-replacement path (no read_note call)."""
        orchestrator._vault_index.get_note_path.return_value = Path("Meetings/Curinos.md")

        rest_client = AsyncMock()

        result = await orchestrator._execute_tool(
            "upsert_note",
            {
                "note_name": "Curinos",
                "content": "Full replacement content",
                "folder": "Meetings",
                "prepend": None,
            },
            rest_client,
        )

        rest_client.read_note.assert_not_called()
        rest_client.upsert_note.assert_called_once()
        assert "Updated" in result

    @pytest.mark.asyncio
    async def test_prepend_on_new_note_creates_normally(self, orchestrator):
        """prepend=true on a non-existent note ignores the flag and creates normally."""
        orchestrator._vault_index.get_note_path.return_value = None

        rest_client = AsyncMock()

        result = await orchestrator._execute_tool(
            "upsert_note",
            {
                "note_name": "NewCompany",
                "content": "## 02/20/2026\n**With:** Bob\nFirst meeting",
                "folder": "Meetings",
                "prepend": True,
            },
            rest_client,
        )

        rest_client.read_note.assert_not_called()
        rest_client.upsert_note.assert_called_once()
        assert "Created" in result
