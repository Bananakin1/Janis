"""End-to-end style tests for bot request routing."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.adapters.base import AgentResponse
from src.bot.client import ObsidianBot


@pytest.fixture
def e2e_settings(temp_vault, tmp_path):
    settings = MagicMock()
    settings.discord_token = "test-token"
    settings.discord_channel_id = 123456789012345678
    settings.discord_guild_id = None
    settings.obsidian_vault_path = temp_vault
    settings.obsidian_api_url = "https://127.0.0.1:27124"
    settings.obsidian_api_key = "test-key"
    settings.azure_openai_endpoint = "https://test.openai.azure.com"
    settings.azure_openai_api_key = "test-azure-key"
    settings.azure_openai_deployment = "gpt-4o"
    settings.llm_provider = "azure_openai"
    settings.obsidian_cli_command = "obsidian"
    settings.default_note_folder = "Inbox"
    settings.reasoning_effort = "medium"
    settings.memory_db_path = tmp_path / "memory.db"
    settings.memory_summary_interval = 10
    settings.max_tool_iterations = 4
    settings.prompt_cache_ttl_seconds = 60
    settings.vault_conventions_note_path = "Vault Conventions"
    settings.tag_registry_note_path = "Tag Registry"
    return settings


@pytest.fixture
def mock_bot_user():
    user = MagicMock()
    user.id = 999999999999999999
    user.__eq__ = lambda self, other: hasattr(other, "id") and other.id == 999999999999999999
    return user


@pytest.mark.asyncio
async def test_message_flows_from_discord_to_orchestrator_and_back(
    e2e_settings,
    mock_discord_message,
    mock_bot_user,
):
    with patch("src.bot.client.Orchestrator") as MockOrchestrator:
        orchestrator = AsyncMock()
        orchestrator.process_request.return_value = AgentResponse(text="I found your notes.")
        MockOrchestrator.return_value = orchestrator
        bot = ObsidianBot(e2e_settings)

        with patch.object(type(bot), "user", new_callable=PropertyMock) as mock_user:
            mock_user.return_value = mock_bot_user
            message = mock_discord_message("Find my meeting notes", channel_id=123456789012345678)
            message.channel.typing.return_value.__aenter__ = AsyncMock()
            message.channel.typing.return_value.__aexit__ = AsyncMock()

            await bot.on_message(message)

    orchestrator.process_request.assert_called_once()
    message.reply.assert_called_once_with("I found your notes.")


@pytest.mark.asyncio
async def test_orchestrator_exceptions_return_generic_error(
    e2e_settings,
    mock_discord_message,
    mock_bot_user,
):
    with patch("src.bot.client.Orchestrator") as MockOrchestrator:
        orchestrator = AsyncMock()
        orchestrator.process_request.side_effect = RuntimeError("boom")
        MockOrchestrator.return_value = orchestrator
        bot = ObsidianBot(e2e_settings)

        with patch.object(type(bot), "user", new_callable=PropertyMock) as mock_user:
            mock_user.return_value = mock_bot_user
            message = mock_discord_message("Do something", channel_id=123456789012345678)
            message.channel.typing.return_value.__aenter__ = AsyncMock()
            message.channel.typing.return_value.__aexit__ = AsyncMock(return_value=False)

            await bot.on_message(message)

    message.reply.assert_called_once_with("An error occurred while processing the request.")
