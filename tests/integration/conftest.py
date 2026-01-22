"""Shared fixtures for integration tests."""

import os
import tempfile
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def temp_vault() -> Generator[Path, None, None]:
    """Create a temporary vault directory with sample notes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault_path = Path(tmpdir)

        # Create folder structure
        (vault_path / "Meetings").mkdir()
        (vault_path / "Centring").mkdir()
        (vault_path / "Records").mkdir()

        # Create sample notes
        (vault_path / "Meetings" / "Team Standup.md").write_text(
            """---
title: Team Standup
type: meeting
tags: [meeting, team]
created: 2024-01-15
related: [[Sarah Chen]], [[Project Alpha]]
---

# Team Standup

Daily standup meeting notes.

## Attendees
- [[Sarah Chen]]
- [[John Smith]]

## Discussion
- Discussed [[Project Alpha]] timeline
"""
        )

        (vault_path / "Meetings" / "Sarah Chen.md").write_text(
            """---
title: Sarah Chen
type: person
tags: [person, engineering]
created: 2024-01-10
related: [[Project Alpha]]
---

# Sarah Chen

Senior Engineer on the platform team.
"""
        )

        (vault_path / "Meetings" / "John Smith.md").write_text(
            """---
title: John Smith
type: person
tags: [person, product]
created: 2024-01-10
related: []
---

# John Smith

Product Manager.
"""
        )

        (vault_path / "Centring" / "Project Alpha.md").write_text(
            """---
title: Project Alpha
type: project
tags: [project, active]
created: 2024-01-01
related: [[Sarah Chen]]
---

# Project Alpha

Main project for Q1.
"""
        )

        (vault_path / "Records" / "Quick Note.md").write_text(
            """---
title: Quick Note
type: general
tags: []
created: 2024-01-20
related: []
---

# Quick Note

Just a quick note.
"""
        )

        yield vault_path


@pytest.fixture
def mock_env_vars(temp_vault: Path) -> Generator[dict, None, None]:
    """Set up mock environment variables for testing."""
    env_vars = {
        "DISCORD_TOKEN": "test-discord-token",
        "DISCORD_CHANNEL_ID": "123456789012345678",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com",
        "AZURE_OPENAI_API_KEY": "test-azure-key",
        "AZURE_OPENAI_DEPLOYMENT": "gpt-4o",
        "OBSIDIAN_VAULT_PATH": str(temp_vault),
        "OBSIDIAN_API_HOST": "127.0.0.1",
        "OBSIDIAN_API_PORT": "27124",
        "OBSIDIAN_API_KEY": "test-obsidian-key",
        "DEFAULT_NOTE_FOLDER": "Inbox",
        "REASONING_EFFORT": "medium",
    }

    with patch.dict(os.environ, env_vars, clear=False):
        yield env_vars


@pytest.fixture
def mock_llm_response():
    """Create a mock LLM response factory for Responses API format."""

    def create_response(content: str = None, tool_calls: list = None):
        response = MagicMock()
        response.output_text = content

        if tool_calls:
            response.output = tool_calls
        else:
            response.output = []

        return response

    return create_response


@pytest.fixture
def mock_tool_call():
    """Create a mock tool call factory for Responses API format."""

    def create_tool_call(call_id: str, name: str, arguments: str):
        tool_call = MagicMock()
        tool_call.type = "function_call"
        tool_call.call_id = call_id
        tool_call.name = name
        tool_call.arguments = arguments
        tool_call.model_dump.return_value = {
            "type": "function_call",
            "call_id": call_id,
            "name": name,
            "arguments": arguments,
        }
        return tool_call

    return create_tool_call


@pytest.fixture
def mock_discord_message():
    """Create a mock Discord message factory."""

    def create_message(
        content: str,
        author_id: int = 111111111111111111,
        author_name: str = "TestUser",
        channel_id: int = 123456789012345678,
        is_bot: bool = False,
    ):
        message = MagicMock()
        message.content = content
        # Create author as a separate mock with explicit equality
        author = MagicMock()
        author.id = author_id
        author.name = author_name
        author.bot = is_bot
        # Configure __eq__ to compare by id (mock wrapper passes self first)
        author.__eq__ = lambda self, other: (
            hasattr(other, 'id') and author_id == other.id
        )
        message.author = author
        message.channel.id = channel_id
        message.channel.typing.return_value = AsyncMock()
        message.reply = AsyncMock()
        return message

    return create_message
