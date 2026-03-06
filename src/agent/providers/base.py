"""Provider abstraction for LLM integrations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ToolCall:
    """One requested tool invocation from the provider."""

    call_id: str
    name: str
    arguments: str


@dataclass(slots=True)
class ProviderResponse:
    """Normalized response returned by an LLM provider."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_output_items: list[dict[str, Any]] = field(default_factory=list)


class LLMProvider(Protocol):
    """Contract implemented by provider adapters."""

    async def generate(
        self,
        input_items: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        """Generate a response for the current loop iteration."""

    async def summarize(self, conversation_text: str) -> str:
        """Produce a compressed summary of a conversation transcript."""
