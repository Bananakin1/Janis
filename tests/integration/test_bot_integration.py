"""Integration tests for Discord bot message handling."""

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from src.bot.client import ObsidianBot, split_message


class TestSplitMessage:
    """Tests for message splitting functionality."""

    def test_short_message_not_split(self):
        """Test messages under limit are not split."""
        message = "This is a short message."
        chunks = split_message(message)

        assert len(chunks) == 1
        assert chunks[0] == message

    def test_long_message_split_at_newline(self):
        """Test long messages are split at newline boundaries."""
        lines = ["Line " + str(i) for i in range(100)]
        message = "\n".join(lines)
        chunks = split_message(message, max_length=500)

        assert len(chunks) > 1
        # Verify no chunk exceeds limit
        for chunk in chunks:
            assert len(chunk) <= 500

    def test_long_message_split_at_space(self):
        """Test messages without newlines split at spaces."""
        words = ["word"] * 500
        message = " ".join(words)
        chunks = split_message(message, max_length=100)

        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 100

    def test_very_long_word_force_split(self):
        """Test very long words are force-split at limit."""
        message = "a" * 300
        chunks = split_message(message, max_length=100)

        assert len(chunks) == 3
        assert chunks[0] == "a" * 100
        assert chunks[1] == "a" * 100
        assert chunks[2] == "a" * 100

    def test_exact_limit_not_split(self):
        """Test message exactly at limit is not split."""
        message = "x" * 2000
        chunks = split_message(message, max_length=2000)

        assert len(chunks) == 1

    def test_preserves_content(self):
        """Test that all content is preserved after splitting."""
        message = "Hello\nWorld\nThis is a test\nWith multiple lines"
        chunks = split_message(message, max_length=20)

        rejoined = "".join(chunks)
        # Account for whitespace stripping
        assert "Hello" in rejoined
        assert "World" in rejoined
        assert "test" in rejoined


@pytest.fixture
def bot_settings(temp_vault):
    """Create mock settings for bot tests."""
    settings = MagicMock()
    settings.discord_token = "test-token"
    settings.discord_channel_id = 123456789012345678
    settings.obsidian_vault_path = temp_vault
    settings.obsidian_api_url = "https://127.0.0.1:27124"
    settings.obsidian_api_key = "test-key"
    settings.azure_openai_endpoint = "https://test.openai.azure.com/"
    settings.azure_openai_api_key = "test-azure-key"
    settings.azure_openai_api_version = "2024-08-01-preview"
    settings.azure_openai_deployment = "gpt-4o"
    settings.default_note_folder = "Inbox"
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


class TestObsidianBotMessageHandling:
    """Integration tests for bot message handling."""

    @pytest.mark.asyncio
    async def test_ignores_own_messages(self, bot_settings, mock_discord_message, mock_bot_user):
        """Test bot ignores its own messages."""
        with patch("src.bot.client.Orchestrator"):
            bot = ObsidianBot(bot_settings)

            # Patch the user property
            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                # Message from bot itself
                message = mock_discord_message("Hello", author_id=999999999999999999)
                message.author = mock_bot_user

                await bot.on_message(message)

                # Should not reply to itself
                message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_other_channels(self, bot_settings, mock_discord_message, mock_bot_user):
        """Test bot ignores messages from other channels."""
        with patch("src.bot.client.Orchestrator"):
            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                # Message from different channel
                message = mock_discord_message(
                    "Hello",
                    channel_id=987654321098765432  # Different from settings
                )

                await bot.on_message(message)

                message.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_ignores_empty_messages(self, bot_settings, mock_discord_message, mock_bot_user):
        """Test bot ignores empty or whitespace messages."""
        with patch("src.bot.client.Orchestrator"):
            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                # Empty message
                message = mock_discord_message("")
                await bot.on_message(message)
                message.reply.assert_not_called()

                # Whitespace only
                message2 = mock_discord_message("   \n\t  ")
                await bot.on_message(message2)
                message2.reply.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_valid_message(self, bot_settings, mock_discord_message, mock_bot_user):
        """Test bot processes valid messages from correct channel."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_message.return_value = "I created the note."
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "Create a note about today's meeting",
                    channel_id=123456789012345678
                )

                # Mock typing context manager
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock()

                await bot.on_message(message)

                # Verify orchestrator was called
                mock_orchestrator.process_message.assert_called_once_with(
                    "Create a note about today's meeting"
                )

                # Verify reply was sent
                message.reply.assert_called_once_with("I created the note.")

    @pytest.mark.asyncio
    async def test_splits_long_responses(self, bot_settings, mock_discord_message, mock_bot_user):
        """Test bot splits long responses into multiple messages."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            # Create a response longer than Discord's limit
            long_response = "x" * 2500

            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_message.return_value = long_response
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "Give me a long response",
                    channel_id=123456789012345678
                )
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock()

                await bot.on_message(message)

                # Should have multiple reply calls
                assert message.reply.call_count == 2

    @pytest.mark.asyncio
    async def test_handles_orchestrator_error(self, bot_settings, mock_discord_message, mock_bot_user):
        """Test bot handles orchestrator errors gracefully."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_message.side_effect = ValueError("Test error")
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "This will cause an error",
                    channel_id=123456789012345678
                )
                message.channel.typing.return_value.__aenter__ = AsyncMock()
                message.channel.typing.return_value.__aexit__ = AsyncMock(return_value=False)

                await bot.on_message(message)

                # Should reply with error message
                message.reply.assert_called_once()
                error_reply = message.reply.call_args[0][0]
                assert "error" in error_reply.lower()

    @pytest.mark.asyncio
    async def test_shows_typing_indicator(self, bot_settings, mock_discord_message, mock_bot_user):
        """Test bot shows typing indicator while processing."""
        with patch("src.bot.client.Orchestrator") as MockOrchestrator:
            mock_orchestrator = AsyncMock()
            mock_orchestrator.process_message.return_value = "Done"
            MockOrchestrator.return_value = mock_orchestrator

            bot = ObsidianBot(bot_settings)

            with patch.object(type(bot), 'user', new_callable=PropertyMock) as mock_user:
                mock_user.return_value = mock_bot_user

                message = mock_discord_message(
                    "Process this",
                    channel_id=123456789012345678
                )

                typing_context = AsyncMock()
                message.channel.typing.return_value = typing_context

                await bot.on_message(message)

                # Verify typing was used
                message.channel.typing.assert_called_once()


class TestObsidianBotInitialization:
    """Tests for bot initialization."""

    def test_bot_initializes_with_correct_intents(self, bot_settings):
        """Test bot initializes with message content intent."""
        with patch("src.bot.client.Orchestrator"):
            bot = ObsidianBot(bot_settings)

            assert bot.intents.message_content is True

    def test_bot_stores_channel_id(self, bot_settings):
        """Test bot stores configured channel ID."""
        with patch("src.bot.client.Orchestrator"):
            bot = ObsidianBot(bot_settings)

            assert bot._channel_id == 123456789012345678
