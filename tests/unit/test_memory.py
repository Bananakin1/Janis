"""Unit tests for SQLite-backed memory."""

from pathlib import Path

import pytest

from src.agent.memory import MemoryStore


class DummyProvider:
    async def summarize(self, conversation_text: str) -> str:
        return f"summary: {conversation_text.splitlines()[0]}"


def test_memory_persists_messages(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db")
    store.add_message("u1", "User", "user", "hello")
    store.add_message("u1", "Janis", "assistant", "hi")

    messages = store.get_recent_messages("u1")
    assert len(messages) == 2
    assert messages[0].content == "hello"
    assert messages[1].content == "hi"


def test_latest_summary_round_trip(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db")
    store.save_summary("u1", "remember Curinos", 2)
    assert store.get_latest_summary("u1") == "remember Curinos"


@pytest.mark.asyncio
async def test_maybe_summarize_creates_summary(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db", summary_interval=2)
    store.add_message("u1", "User", "user", "Read Curinos")
    store.add_message("u1", "Janis", "assistant", "Here it is")

    summary = await store.maybe_summarize("u1", DummyProvider())

    assert summary is not None
    assert "summary:" in summary
    assert store.get_latest_summary("u1") == summary
