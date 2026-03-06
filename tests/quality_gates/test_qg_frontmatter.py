"""Quality gates for frontmatter property updates."""

import pytest


pytestmark = pytest.mark.qg


@pytest.mark.asyncio
async def test_qg4_frontmatter_update(qg_harness, snapshot_note):
    await snapshot_note("02 Specs/SPEC-meeting-intelligence.md")
    result = await qg_harness.run(
        "Mark SPEC-meeting-intelligence as shipped and set its branch to "
        "feature/whiteboard-projectmem-precedent-meeting"
    )

    has_set_property = result.has_tool_call("set_property", key="status", value="shipped")
    has_patch = result.has_tool_call("patch_note") or result.find_write_call("SPEC-meeting-intelligence") is not None
    assert has_set_property or has_patch, (
        f"Expected set_property or patch_note/write for frontmatter update, "
        f"got: {[tc.name for tc in result.tool_calls]}"
    )
    assert "shipped" in str(result.tool_calls).lower() or "shipped" in result.response.lower()
