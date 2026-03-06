"""Quality gates for convention-aware note creation."""

import pytest


pytestmark = pytest.mark.qg


@pytest.mark.asyncio
async def test_qg8_decision_record_creation(qg_harness):
    result = await qg_harness.run(
        "Create a decision record about choosing SQLite over PostgreSQL for Janis's memory store."
    )
    write_call = result.find_write_call("ADR") or result.find_write_call("decision") or result.find_write_call("SQLite")
    if write_call is not None:
        assert "decision" in write_call.content.lower() or "type: decision" in write_call.content
    else:
        assert result.has_tool_call("read_note", note_name_contains="ADR") or \
            result.has_tool_call("read_note", note_name_contains="decision"), (
            f"Expected a write or read of a decision record, got: "
            f"{[tc.name + '(' + str(tc.args) + ')' for tc in result.tool_calls]}"
        )


@pytest.mark.asyncio
async def test_qg10_respects_centring_boundary(qg_harness):
    result = await qg_harness.run(
        "Create a spec for the new search optimization feature and link it to the RAG refinement "
        "note in the Centring folder"
    )
    write_call = result.find_write_call("Spec") or result.find_write_call("search") or result.find_write_call("optimization")
    if write_call is not None:
        assert "[[RAG refinement]]" not in write_call.content, (
            "Write call should not cross-link into the Centring folder"
        )
