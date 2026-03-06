"""Tool registry with auto-discovery for `src.tools` modules."""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterable
from pathlib import Path

from src.errors import BackendUnavailableError
from src.tools.base import ToolContext, ToolDefinition, ToolResult


class ToolRegistry:
    """Registry of discovered tool definitions."""

    def __init__(self, tools: Iterable[ToolDefinition] | None = None) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        if tools:
            for tool in tools:
                self.register(tool)

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)

    def get_schemas(self, ctx: ToolContext | None = None) -> list[dict]:
        return [
            tool.schema()
            for tool in self._tools.values()
            if tool.available(ctx)
        ]

    async def execute(self, name: str, args: dict, ctx: ToolContext) -> ToolResult:
        tool = self.get(name)
        if tool.requires_cli and (ctx.cli is None or not ctx.cli.is_available()):
            raise BackendUnavailableError("Obsidian CLI is not available.")
        params = tool.params_model.model_validate(args)
        result = await tool.execute(params, ctx)
        if isinstance(result, ToolResult):
            return result
        return ToolResult(content=str(result))

    @classmethod
    def discover(cls, package: str = "src.tools") -> "ToolRegistry":
        package_module = importlib.import_module(package)
        registry = cls()
        package_path = Path(package_module.__file__).parent
        for module_info in pkgutil.iter_modules([str(package_path)]):
            if module_info.name in {"base", "registry", "__init__"}:
                continue
            module = importlib.import_module(f"{package}.{module_info.name}")
            tool = getattr(module, "tool", None)
            if isinstance(tool, ToolDefinition):
                registry.register(tool)
        return registry
