"""Discord UI views for interactive Janis responses."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

import discord

from src.adapters.base import PendingAction


InteractionHandler = Callable[[discord.Interaction, str, PendingAction], Awaitable[None]]


class ActionView(discord.ui.View):
    """Dynamic button view for a pending action."""

    def __init__(self, action: PendingAction, handler: InteractionHandler) -> None:
        super().__init__(timeout=120)
        self._action = action
        self._handler = handler

        for option in action.options[:5]:
            style = {
                "primary": discord.ButtonStyle.primary,
                "secondary": discord.ButtonStyle.secondary,
                "danger": discord.ButtonStyle.danger,
                "success": discord.ButtonStyle.success,
            }.get(option.style, discord.ButtonStyle.secondary)
            button = discord.ui.Button(label=option.label, style=style)

            async def callback(interaction: discord.Interaction, value: str = option.value) -> None:
                await self._handler(interaction, value, self._action)

            button.callback = callback
            self.add_item(button)
