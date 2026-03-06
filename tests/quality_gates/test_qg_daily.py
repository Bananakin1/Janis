"""Quality gates for daily note flows."""

import pytest


pytestmark = pytest.mark.qg


@pytest.mark.asyncio
async def test_qg3_daily_note_append(qg_harness):
    result = await qg_harness.run(
        "Add to my daily note: follow up with Morris about the onboarding package by Friday"
    )

    assert result.has_tool_call("daily_append") or result.has_tool_call("append_daily")
    assert "Morris" in str(result.tool_calls)
