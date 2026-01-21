"""End-to-end integration tests for message processing flow."""

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from pytest_httpx import HTTPXMock

from src.bot.client import ObsidianBot
from src.config.settings import Settings


@pytest.fixture
def e2e_settings(temp_vault):
    """Create settings for end-to-end tests."""
    settings = MagicMock(spec=Settings)
    settings.obsidian_vault_path = temp_vault
    settings.obsidian_api_url = "https://127.0.0.1:27124"
    settings.obsidian_api_key = "test-key"
    settings.azure_openai_endpoint = "https://test.openai.azure.com/"
    settings.azure_openai_api_key = "test-azure-key"
    settings.azure_openai_api_version = "2024-08-01-preview"
    settings.azure_openai_deployment = "gpt-4o"
    settings.default_note_folder = "Inbox"
    settings.discord_token = "test-token"
    settings.discord_channel_id = 123456789012345678
    return settings


@pytest.fixture
def mock_bot_user():
    """Create a mock user for the bot."""
    user = MagicMock()
    user.id = 999999999999999999
    # Configure __eq__ to compare by id (mock wrapper passes self first)
    user.__eq__ = lambda self, other: (
        hasattr(other, 'id') and 999999999999999999 == other.id
    )
    return user


class TestEndToEndBotResponse:
    """End-to-end tests for bot processing a message and responding."""

    @pytest.mark.asyncio
    async def test_bot_processes_message_and_replies(
        self, e2e_settings, mock_discord_message, mock_bot_user
    ):
        """Test complete flow: Discord message -> orchestrator -> reply."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_message.return_value = "I found your notes."
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(e2e_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "Find my meeting notes",
                    channel_id=123456789012345678
                )
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock()

                await bot.on_message(message)

                # Verify the full flow
                mock_orchestrator.process_message.assert_called_once_with(
                    "Find my meeting notes"
                )
                message.reply.assert_called_once_with("I found your notes.")


class TestEndToEndErrorHandling:
    """End-to-end tests for error handling."""

    @pytest.mark.asyncio
    async def test_obsidian_offline_returns_error_to_user(
        self, e2e_settings, mock_discord_message, mock_bot_user
    ):
        """Test that Obsidian offline error reaches the user."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_message.return_value = (
                "Obsidian is not running. Please open it and try again."
            )
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(e2e_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "Create a note",
                    channel_id=123456789012345678
                )
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock()

                await bot.on_message(message)

                reply = message.reply.call_args[0][0]
                assert "Obsidian is not running" in reply

    @pytest.mark.asyncio
    async def test_orchestrator_exception_returns_error_to_user(
        self, e2e_settings, mock_discord_message, mock_bot_user
    ):
        """Test that orchestrator exceptions are caught and reported."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_message.side_effect = Exception("LLM API error")
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(e2e_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "Do something",
                    channel_id=123456789012345678
                )
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock(return_value=False)

                await bot.on_message(message)

                message.reply.assert_called_once()
                reply = message.reply.call_args[0][0]
                assert "error" in reply.lower()


class TestEndToEndMessageFiltering:
    """End-to-end tests for message filtering."""

    @pytest.mark.asyncio
    async def test_ignores_wrong_channel(
        self, e2e_settings, mock_discord_message, mock_bot_user
    ):
        """Test that messages from wrong channel are ignored."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(e2e_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                # Wrong channel
                message = mock_discord_message(
                    "Hello",
                    channel_id=999999999999999999
                )

                await bot.on_message(message)

                mock_orchestrator.process_message.assert_not_called()
                message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_empty_messages(
        self, e2e_settings, mock_discord_message, mock_bot_user
    ):
        """Test that empty messages are ignored."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(e2e_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "   ",
                    channel_id=123456789012345678
                )

                await bot.on_message(message)

                mock_orchestrator.process_message.assert_not_called()
