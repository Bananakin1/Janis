"""Integration tests for Orchestrator."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent.orchestrator import Orchestrator, INVALID_CHARS
from src.config.settings import Settings


@pytest.fixture
def mock_settings(temp_vault):
    """Create mock settings with temp vault."""
    settings = MagicMock(spec=Settings)
    settings.obsidian_vault_path = temp_vault
    settings.obsidian_api_url = "https://127.0.0.1:27124"
    settings.obsidian_api_key = "test-key"
    settings.azure_openai_endpoint = "https://test.openai.azure.com"
    settings.azure_openai_api_key = "test-azure-key"
    settings.azure_openai_deployment = "gpt-4o"
    settings.default_note_folder = "Inbox"
    settings.reasoning_effort = "medium"
    return settings


class TestOrchestratorHealthCheck:
    """Integration tests for orchestrator health check."""

    @pytest.mark.asyncio
    async def test_check_health_returns_healthy(self, mock_settings):
        """Test check_health returns True when services are up."""
        with patch("src.agent.orchestrator.AsyncOpenAI"), \
             patch("src.agent.orchestrator.VaultIndex"), \
             patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:

            mock_client = AsyncMock()
            mock_client.health_check.return_value = True
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            orchestrator = Orchestrator(mock_settings)
            is_healthy, error = await orchestrator.check_health()

            assert is_healthy is True
            assert error is None

    @pytest.mark.asyncio
    async def test_check_health_returns_unhealthy(self, mock_settings):
        """Test check_health returns False with error message when down."""
        with patch("src.agent.orchestrator.AsyncOpenAI"), \
             patch("src.agent.orchestrator.VaultIndex"), \
             patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:

            mock_client = AsyncMock()
            mock_client.health_check.return_value = False
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            orchestrator = Orchestrator(mock_settings)
            is_healthy, error = await orchestrator.check_health()

            assert is_healthy is False
            assert error is not None
            assert "not available" in error


class TestOrchestratorSanitization:
    """Tests for note name sanitization."""

    @pytest.fixture
    def orchestrator(self, mock_settings):
        """Create orchestrator with mocked dependencies."""
        with patch("src.agent.orchestrator.VaultIndex"), \
             patch("src.agent.orchestrator.AsyncOpenAI"):
            return Orchestrator(mock_settings)

    def test_sanitize_replaces_invalid_chars(self, orchestrator):
        """Test that invalid characters are replaced."""
        assert "/" not in orchestrator._sanitize_note_name("foo/bar")
        assert ":" not in orchestrator._sanitize_note_name("Meeting: 2024")
        assert "?" not in orchestrator._sanitize_note_name("What?")
        assert "*" not in orchestrator._sanitize_note_name("Test*File")

    def test_sanitize_preserves_valid_chars(self, orchestrator):
        """Test that valid characters are preserved."""
        result = orchestrator._sanitize_note_name("Valid Note-Name_v2")
        assert result == "Valid Note-Name_v2"


class TestOrchestratorObsidianOffline:
    """Tests for Obsidian offline handling."""

    @pytest.mark.asyncio
    async def test_returns_error_when_obsidian_offline(self, mock_settings):
        """Test orchestrator returns error when Obsidian is offline."""
        with patch("src.agent.orchestrator.AsyncOpenAI"), \
             patch("src.agent.orchestrator.VaultIndex") as MockVaultIndex, \
             patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:

            # Mock vault index
            mock_vault_index = MagicMock()
            mock_vault_index.get_vault_summary.return_value = {
                "total_notes": 0, "folders": [], "recent_notes": []
            }
            mock_vault_index.get_hub_notes.return_value = []
            MockVaultIndex.return_value = mock_vault_index

            # Mock REST client - offline
            mock_client = AsyncMock()
            mock_client.health_check.return_value = False
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            orchestrator = Orchestrator(mock_settings)
            result = await orchestrator.process_message("Create a note")

            assert "Obsidian is not running" in result


class TestOrchestratorDirectResponse:
    """Tests for direct LLM responses without tool calls."""

    @pytest.mark.asyncio
    async def test_returns_llm_response_without_tools(self, mock_settings):
        """Test orchestrator returns LLM response when no tools needed."""
        with patch("src.agent.orchestrator.AsyncOpenAI") as MockLLM, \
             patch("src.agent.orchestrator.VaultIndex") as MockVaultIndex, \
             patch("src.agent.orchestrator.ObsidianRESTClient") as MockClient:

            # Mock vault index
            mock_vault_index = MagicMock()
            mock_vault_index.get_vault_summary.return_value = {
                "total_notes": 5, "folders": ["Inbox"], "recent_notes": []
            }
            mock_vault_index.get_hub_notes.return_value = []
            MockVaultIndex.return_value = mock_vault_index

            # Mock REST client - online
            mock_client = AsyncMock()
            mock_client.health_check.return_value = True
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            MockClient.return_value = mock_client

            # Mock LLM - Responses API format (no tool calls)
            mock_llm = MagicMock()
            mock_response = MagicMock()
            mock_response.output = []  # No function calls
            mock_response.output_text = "Hello! How can I help?"
            mock_llm.responses.create = AsyncMock(return_value=mock_response)
            MockLLM.return_value = mock_llm

            orchestrator = Orchestrator(mock_settings)
            result = await orchestrator.process_message("Hello")

            assert result == "Hello! How can I help?"
