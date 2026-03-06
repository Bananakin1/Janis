"""Discord embed helpers."""

from __future__ import annotations

import discord


def build_note_preview_embed(path: str, content: str) -> discord.Embed:
    """Build a compact embed preview for a note."""
    preview = content.strip()
    if len(preview) > 1000:
        preview = f"{preview[:997]}..."
    embed = discord.Embed(title=path, description=preview or "(empty note)")
    embed.set_footer(text="Janis note preview")
    return embed


def build_search_results_embed(title: str, results: list[str]) -> discord.Embed:
    """Build an embed for search or browse results."""
    description = "\n".join(results[:20]) or "No results."
    embed = discord.Embed(title=title, description=description)
    embed.set_footer(text=f"{len(results)} item(s)")
    return embed
