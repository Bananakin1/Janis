"""Backward-compatible import path for the Discord adapter."""

from src.adapters.discord.client import MAX_MESSAGE_LENGTH, ObsidianBot as DiscordObsidianBot, split_message
from src.agent.orchestrator import Orchestrator


class ObsidianBot(DiscordObsidianBot):
    """Compatibility wrapper that preserves the historical constructor surface."""

    def __init__(self, settings) -> None:
        super().__init__(settings, orchestrator=Orchestrator(settings))


__all__ = ["MAX_MESSAGE_LENGTH", "ObsidianBot", "Orchestrator", "split_message"]
