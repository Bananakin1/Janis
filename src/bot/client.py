"""Discord bot implementation."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from src.config.settings import Settings
from src.agent.orchestrator import Orchestrator


logger = logging.getLogger(__name__)

# Discord message character limit
MAX_MESSAGE_LENGTH = 2000


def split_message(content: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks that fit Discord's limit.

    Args:
        content: Message content to split.
        max_length: Maximum length per chunk.

    Returns:
        List of message chunks.
    """
    if len(content) <= max_length:
        return [content]

    chunks = []
    while content:
        if len(content) <= max_length:
            chunks.append(content)
            break

        # Find a good break point (newline or space)
        split_at = content.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = content.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length

        chunks.append(content[:split_at])
        content = content[split_at:].lstrip()

    return chunks


class ObsidianBot(commands.Bot):
    """Discord bot for interacting with Obsidian vault."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the bot.

        Args:
            settings: Application settings.
        """
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

        self._settings = settings
        self._orchestrator = Orchestrator(settings)
        self._channel_id = settings.discord_channel_id

    async def on_ready(self) -> None:
        """Handle bot ready event."""
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info(f"Listening on channel ID: {self._channel_id}")

    async def on_message(self, message: discord.Message) -> None:
        """Handle incoming messages.

        Args:
            message: Discord message object.
        """
        # Ignore messages from the bot itself
        if message.author == self.user:
            return

        # Only respond in the configured channel
        if message.channel.id != self._channel_id:
            return

        # Build content from message text and any text file attachments
        content = message.content.strip()

        # Read text file attachments (e.g., message.txt from long Discord pastes)
        for attachment in message.attachments:
            if attachment.filename.endswith(".txt"):
                try:
                    file_bytes = await attachment.read()
                    file_text = file_bytes.decode("utf-8")
                    content = f"{content}\n\n{file_text}".strip()
                    logger.info(f"Read attachment: {attachment.filename} ({len(file_text)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to read attachment {attachment.filename}: {e}")

        # Ignore empty messages
        if not content:
            return

        logger.info(f"Processing message from {message.author}: {content[:50]}...")

        try:
            # Show typing indicator while processing
            async with message.channel.typing():
                response = await self._orchestrator.process_message(content, author=message.author.display_name)

                # Send response (split if needed)
                chunks = split_message(response)
                for chunk in chunks:
                    await message.reply(chunk)

        except Exception as e:
            logger.exception("Error processing message")
            error_msg = f"An error occurred: {type(e).__name__}"
            await message.reply(error_msg)

    def run_bot(self) -> None:
        """Start the bot with the configured token."""
        self.run(self._settings.discord_token)
