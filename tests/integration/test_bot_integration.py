"""Integration tests for Discord bot message handling."""

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from src.adapters.base import AgentResponse
from src.bot.client import ObsidianBot, split_message


class TestSplitMessage:
    def test_short_message_not_split(self):
        assert split_message("short") == ["short"]

    def test_long_message_is_split(self):
        message = "a" * 2100
        chunks = split_message(message)
        assert len(chunks) == 2
        assert all(len(chunk) <= 2000 for chunk in chunks)


@pytest.fixture
def bot_settings(temp_vault, tmp_path):
    settings = MagicMock()
    settings.discord_token = "test-token"
    settings.discord_channel_id = 123456789012345678
    settings.discord_guild_id = None
    settings.obsidian_vault_path = temp_vault
    settings.obsidian_api_url = "https://127.0.0.1:27124"
    settings.obsidian_api_key = "test-key"
    settings.azure_openai_endpoint = "https://test.openai.azure.com/"
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


class TestObsidianBotMessageHandling:
    @pytest.mark.asyncio
    async def test_ignores_own_messages(self, bot_settings, mock_discord_message, mock_bot_user):
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            MockOrchestrator.return_value = AsyncMock()
            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), "user", new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user
                message = mock_discord_message("Hello", author_id=999999999999999999)
                message.author = mock_bot_user
                await bot.on_message(message)

        message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_valid_message(self, bot_settings, mock_discord_message, mock_bot_user):
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_request.return_value = AgentResponse(text="I created the note.")
            MockOrchestrator.return_value = mock_orchestrator
            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), "user", new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user
                message = mock_discord_message(
                    "Create a note",
                    channel_id=123456789012345678,
                )
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock()

                await bot.on_message(message)

        mock_orchestrator.process_request.assert_called_once()
        message.reply.assert_called_once_with("I created the note.")

    @pytest.mark.asyncio
    async def test_long_response_is_sent_as_file(self, bot_settings, mock_discord_message, mock_bot_user):
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_request.return_value = AgentResponse(text="x" * 2501)
            MockOrchestrator.return_value = mock_orchestrator
            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), "user", new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user
                message = mock_discord_message("Long reply", channel_id=123456789012345678)
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock()

                await bot.on_message(message)

        kwargs = message.reply.call_args.kwargs
        assert kwargs["content"] == "Attached response."
        assert "file" in kwargs
