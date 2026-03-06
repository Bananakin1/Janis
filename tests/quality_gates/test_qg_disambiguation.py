"""Quality gates for disambiguation behavior."""

import pytest


pytestmark = pytest.mark.qg


@pytest.mark.asyncio
async def test_qg7_disambiguation(qg_harness):
    result = await qg_harness.run("Read the agent note")
    assert result.has_tool_call("search_notes")
    assert result.has_tool_call("ask_clarification")
