"""Base types for Janis tool definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from pydantic import BaseModel

from src.adapters.base import AgentRequest, AgentResponse
from src.backend.cli_bridge import ObsidianCLI
from src.backend.rest_client import ObsidianRESTClient
from src.backend.vault_index import VaultIndex


@dataclass(slots=True)
class ToolResult:
    """Structured result returned by a tool."""

    content: str
    stop: bool = False
    response: AgentResponse | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolContext:
    """Runtime dependencies available to tool implementations."""

    settings: Any
    rest: ObsidianRESTClient
    cli: ObsidianCLI | None
    vault_index: VaultIndex
    request: AgentRequest
    memory: Any | None = None
    state: dict[str, Any] = field(default_factory=dict)


ToolExecutor = Callable[[BaseModel, ToolContext], Awaitable[ToolResult | str]]


@dataclass(slots=True)
class ToolDefinition:
    """Declarative tool definition discovered by the registry."""

    name: str
    description: str
    params_model: type[BaseModel]
    execute: ToolExecutor
    strict: bool = True
    requires_cli: bool = False
    _cached_schema: dict[str, Any] | None = field(default=None, repr=False)

    def schema(self) -> dict[str, Any]:
        """Return the OpenAI Responses API function schema.

        When strict mode is enabled, all properties must appear in
        ``required`` and ``additionalProperties`` must be false.
        """
        if self._cached_schema is not None:
            return self._cached_schema
        json_schema = self.params_model.model_json_schema(mode="validation")
        if self.strict:
            json_schema["required"] = sorted(json_schema.get("properties", {}).keys())
            json_schema["additionalProperties"] = False
        self._cached_schema = {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "strict": self.strict,
            "parameters": json_schema,
        }
        return self._cached_schema

    def available(self, ctx: ToolContext | None = None) -> bool:
        """Determine whether this tool is available for the current context."""
        if not self.requires_cli:
            return True
        return ctx is not None and ctx.cli is not None and ctx.cli.is_available()
