"""Quality gates for meeting note flows."""

import re

import pytest


pytestmark = pytest.mark.qg


@pytest.mark.asyncio
async def test_qg1_meeting_append(qg_harness, snapshot_note):
    await snapshot_note("05 Meetings/ITK.md")
    result = await qg_harness.run(
        "I had a meeting with ITK today. Morris Harris was there. We discussed that they're "
        "finalizing the Enterprise Architecture engagement for a new client and Morris wants "
        "the SharePoint integration set up before discovery."
    )

    assert result.has_tool_call("read_note", note_name_contains="ITK") or \
        result.has_tool_call("search_notes", query_contains="ITK")
    write_call = result.find_write_call("ITK")
    assert write_call is not None
    assert re.search(r"## \d{2}/\d{2}/\d{4}", write_call.content)
    assert "Morris Harris" in write_call.content


@pytest.mark.asyncio
async def test_qg2_new_meeting_creation(qg_harness):
    result = await qg_harness.run(
        "Create a meeting note for a new company called Meridian Capital. I met with Sarah Chen "
        "(Managing Director) and David Park (VP, Technology). We discussed their interest in "
        "automating quarterly fund reports using Centring."
    )

    assert result.has_tool_call("search_notes", query_contains="Meridian") or \
        result.has_tool_call("read_note", note_name_contains="Meridian")
    write_call = result.find_write_call("Meridian")
    if write_call is not None:
        assert "type: meeting" in write_call.content
    else:
        assert "Meridian" in result.response
