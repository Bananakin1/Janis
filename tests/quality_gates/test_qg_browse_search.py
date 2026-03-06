"""Quality gates for browse and structured search."""

import pytest


pytestmark = pytest.mark.qg


@pytest.mark.asyncio
async def test_qg5_vault_browse(qg_harness):
    result = await qg_harness.run("What's in the 04 Business folder?")
    assert result.has_tool_call("list_vault", path_contains="04 Business")


@pytest.mark.asyncio
async def test_qg6_structured_search(qg_harness):
    result = await qg_harness.run("Find all specs that are currently in progress")
    assert result.has_tool_call("search_dql") or result.has_tool_call("search_notes")
    assert "in-progress" in result.response.lower() or "in progress" in result.response.lower()
