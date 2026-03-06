"""Quality gates for cross-conversation memory."""

import re

import pytest


pytestmark = pytest.mark.qg


@pytest.mark.asyncio
async def test_qg9_cross_conversation_memory(qg_harness, snapshot_note):
    await snapshot_note("05 Meetings/Curinos.md")
    first = await qg_harness.run("Read the Curinos meeting note")
    second = await qg_harness.run(
        "Add a new meeting to that note. I met with Olly today. He confirmed he wants to join "
        "the board and will recuse from incubator voting."
    )

    assert first.has_tool_call("read_note", note_name_contains="Curinos")
    write_call = second.find_write_call("Curinos")
    assert write_call is not None
    assert "Olly" in write_call.content
    assert re.search(r"## \d{2}/\d{2}/\d{4}", write_call.content)
