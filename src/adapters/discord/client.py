"""Discord adapter implementation."""

from __future__ import annotations

import io
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from src.adapters.base import AgentRequest, AgentResponse
from src.adapters.discord.views import ActionView
from src.agent.orchestrator import Orchestrator
from src.config.settings import Settings


logger = logging.getLogger(__name__)

MAX_MESSAGE_LENGTH = 2000


def split_message(content: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into Discord-sized chunks."""
    if len(content) <= max_length:
        return [content]

    chunks = []
    remaining = content
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, max_length)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, max_length)
        if split_at == -1:
            split_at = max_length
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:].lstrip()
    return chunks


class ObsidianBot(commands.Bot):
    """Discord bot adapter for Janis."""

    def __init__(self, settings: Settings, orchestrator: Orchestrator | None = None) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self._settings = settings
        self._orchestrator = orchestrator or Orchestrator(settings)
        self._channel_id = settings.discord_channel_id
        self._commands_registered = False

    async def setup_hook(self) -> None:
        if not self._commands_registered:
            self._register_commands()
            guild = None
            if self._settings.discord_guild_id:
                guild = discord.Object(id=self._settings.discord_guild_id)
            await self.tree.sync(guild=guild)
            self._commands_registered = True

    def _register_commands(self) -> None:
        guild = discord.Object(id=self._settings.discord_guild_id) if self._settings.discord_guild_id else None

        @self.tree.command(name="note", description="Send a natural-language note request", guild=guild)
        async def note_command(interaction: discord.Interaction, prompt: str) -> None:
            await interaction.response.defer(thinking=True)
            response = await self._orchestrator.process_request(
                AgentRequest(
                    user_id=str(interaction.user.id),
                    user_name=interaction.user.display_name,
                    message=prompt,
                    channel_id=str(interaction.channel_id),
                )
            )
            await self._send_interaction_response(interaction, response)

        @self.tree.command(name="daily", description="Append text to today's daily note", guild=guild)
        async def daily_command(interaction: discord.Interaction, content: str) -> None:
            await interaction.response.defer(thinking=True)
            response = await self._orchestrator.process_request(
                AgentRequest(
                    user_id=str(interaction.user.id),
                    user_name=interaction.user.display_name,
                    message=f"Add to my daily note: {content}",
                    channel_id=str(interaction.channel_id),
                )
            )
            await self._send_interaction_response(interaction, response)

        @self.tree.command(name="search", description="Search the vault in natural language", guild=guild)
        async def search_command(interaction: discord.Interaction, query: str) -> None:
            await interaction.response.defer(thinking=True)
            response = await self._orchestrator.process_request(
                AgentRequest(
                    user_id=str(interaction.user.id),
                    user_name=interaction.user.display_name,
                    message=f"Search the vault for: {query}",
                    channel_id=str(interaction.channel_id),
                )
            )
            await self._send_interaction_response(interaction, response)

    async def _handle_action_click(
        self,
        interaction: discord.Interaction,
        value: str,
        action,
    ) -> None:
        await interaction.response.defer(thinking=True)
        follow_up_message = (
            f"For the previous prompt '{action.prompt}', I choose: {value}."
        )
        response = await self._orchestrator.process_request(
            AgentRequest(
                user_id=str(interaction.user.id),
                user_name=interaction.user.display_name,
                message=follow_up_message,
                channel_id=str(interaction.channel_id),
                metadata={"action_kind": action.kind, "value": value, **action.metadata},
            )
        )
        await self._send_interaction_response(interaction, response)

    async def _send_interaction_response(
        self,
        interaction: discord.Interaction,
        response: AgentResponse,
    ) -> None:
        kwargs = self._build_send_kwargs(response)
        await interaction.followup.send(**kwargs)

    def _build_send_kwargs(self, response: AgentResponse) -> dict:
        kwargs: dict = {}
        text = response.text
        if response.file_content is not None:
            file_name = response.file_name or "janis-response.md"
            kwargs["content"] = text or "Attached."
            kwargs["file"] = discord.File(
                io.BytesIO(response.file_content.encode("utf-8")),
                filename=file_name,
            )
        elif len(text) > MAX_MESSAGE_LENGTH:
            kwargs["content"] = "Attached response."
            kwargs["file"] = discord.File(
                io.BytesIO(text.encode("utf-8")),
                filename=response.file_name or "janis-response.md",
            )
        else:
            kwargs["content"] = text

        if response.action is not None and response.action.options:
            kwargs["view"] = ActionView(response.action, self._handle_action_click)
        return kwargs

    async def _send_channel_response(self, message: discord.Message, response: AgentResponse) -> None:
        kwargs = self._build_send_kwargs(response)
        if "file" in kwargs or "view" in kwargs:
            await message.reply(**kwargs)
            return
        for chunk in split_message(kwargs["content"]):
            await message.reply(chunk)

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (ID: %s)", self.user, getattr(self.user, "id", "unknown"))
        logger.info("Listening on channel ID: %s", self._channel_id)

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        if message.channel.id != self._channel_id:
            return

        content = message.content.strip()
        for attachment in message.attachments:
            if attachment.filename.endswith(".txt"):
                try:
                    file_bytes = await attachment.read()
                    file_text = file_bytes.decode("utf-8")
                    content = f"{content}\n\n{file_text}".strip()
                except Exception:
                    logger.exception("Failed to read attachment %s", attachment.filename)

        if not content:
            return

        try:
            async with message.channel.typing():
                response = await self._orchestrator.process_request(
                    AgentRequest(
                        user_id=str(message.author.id),
                        user_name=message.author.display_name,
                        message=content,
                        channel_id=str(message.channel.id),
                    )
                )
                await self._send_channel_response(message, response)
        except Exception:
            logger.exception("Error processing message")
            await message.reply("An error occurred while processing the request.")

    def run_bot(self) -> None:
        self.run(self._settings.discord_token)
