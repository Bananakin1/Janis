"""Platform-agnostic request and response contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(slots=True)
class ButtonOption:
    """One selectable button option for an interactive response."""

    label: str
    value: str
    style: str = "secondary"


@dataclass(slots=True)
class PendingAction:
    """A platform-agnostic interactive action."""

    kind: str
    prompt: str
    options: list[ButtonOption] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentRequest:
    """Normalized inbound request from any platform."""

    user_id: str
    user_name: str
    message: str
    channel_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResponse:
    """Normalized outbound response returned by the orchestrator."""

    text: str
    action: PendingAction | None = None
    file_name: str | None = None
    file_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AdapterProtocol(Protocol):
    """Contract for platform adapters."""

    async def run(self) -> None:
        """Start the adapter."""
