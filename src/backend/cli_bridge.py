"""Async subprocess bridge for the Obsidian CLI (1.12+)."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass

from src.errors import BackendError, BackendUnavailableError, ValidationFailure


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CLIResult:
    """Parsed result of a CLI invocation."""

    stdout: str
    stderr: str
    returncode: int


class ObsidianCLI:
    """Async subprocess wrapper for Obsidian CLI commands.

    The Obsidian CLI (1.12+) uses ``key=value`` parameter syntax.
    On Windows the terminal redirector is ``Obsidian.com`` which is
    resolved via PATH when the setting is ``obsidian`` (default).
    """

    def __init__(self, command: str = "obsidian") -> None:
        self._command = command
        self._available: bool | None = None

    @property
    def command(self) -> str:
        return self._command

    def is_available(self) -> bool:
        if self._available is None:
            self._available = shutil.which(self._command) is not None
        return self._available

    async def _run(self, *args: str) -> CLIResult:
        if not self.is_available():
            raise BackendUnavailableError(f"Obsidian CLI '{self._command}' is not available.")
        process = await asyncio.create_subprocess_exec(
            self._command,
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr = stderr_bytes.decode("utf-8", errors="replace").strip()
        if process.returncode != 0:
            logger.error(
                "Obsidian CLI failed: %s %s -> %s",
                self._command,
                " ".join(args),
                stderr or stdout,
            )
            raise BackendError(stderr or stdout or "Command failed.")
        return CLIResult(stdout=stdout, stderr=stderr, returncode=process.returncode)

    # --- File operations ---

    async def move(self, source: str, destination: str) -> str:
        """``obsidian move file=<source> to=<destination>``"""
        result = await self._run("move", f"file={source}", f"to={destination}")
        return result.stdout or f"Moved '{source}' to '{destination}'."

    async def rename(self, file: str, name: str) -> str:
        """``obsidian rename file=<file> name=<name>``"""
        result = await self._run("rename", f"file={file}", f"name={name}")
        return result.stdout or f"Renamed '{file}' to '{name}'."

    async def open_note(self, file: str) -> str:
        """``obsidian open file=<file>``"""
        result = await self._run("open", f"file={file}")
        return result.stdout or f"Opened '{file}'."

    # --- Properties ---

    async def set_property(self, file: str, key: str, value: str) -> str:
        """``obsidian property:set name=<key> value=<value> file=<file>``"""
        if not key:
            raise ValidationFailure("Property key cannot be empty.")
        result = await self._run(
            "property:set", f"name={key}", f"value={value}", f"file={file}",
        )
        return result.stdout or f"Set '{key}' on '{file}'."

    async def read_property(self, file: str, key: str) -> str | None:
        """``obsidian property:read name=<key> file=<file>``"""
        result = await self._run("property:read", f"name={key}", f"file={file}")
        return result.stdout or None

    async def remove_property(self, file: str, key: str) -> str:
        """``obsidian property:remove name=<key> file=<file>``"""
        result = await self._run("property:remove", f"name={key}", f"file={file}")
        return result.stdout or f"Removed '{key}' from '{file}'."

    # --- Tags ---

    async def list_tags(self) -> dict[str, int]:
        """``obsidian tags format=json counts``"""
        result = await self._run("tags", "format=json", "counts")
        if not result.stdout:
            return {}
        payload = json.loads(result.stdout)
        if isinstance(payload, dict):
            return {str(k): int(v) for k, v in payload.items()}
        if isinstance(payload, list):
            tags: dict[str, int] = {}
            for item in payload:
                if isinstance(item, dict):
                    name = str(item.get("tag") or item.get("name") or "")
                    count = int(item.get("count") or 0)
                    if name:
                        tags[name] = count
                elif isinstance(item, str):
                    tags[item] = 0
            return tags
        return {}

    # --- Backlinks ---

    async def get_backlinks(self, file: str) -> list[str]:
        """``obsidian backlinks file=<file> format=json``"""
        result = await self._run("backlinks", f"file={file}", "format=json")
        if not result.stdout:
            return []
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if isinstance(payload, list):
            return [str(item) for item in payload]
        if isinstance(payload, dict):
            items = payload.get("backlinks") or payload.get("items") or []
            return [str(item) for item in items]
        return []

    # --- Search ---

    async def search(self, query: str, path: str | None = None, limit: int = 20) -> str:
        """``obsidian search query=<text> [path=<folder>] limit=<n> format=json``"""
        args = ["search", f"query={query}", f"limit={limit}", "format=json"]
        if path:
            args.append(f"path={path}")
        result = await self._run(*args)
        return result.stdout

    # --- Templates ---

    async def create_from_template(self, name: str, template: str, folder: str) -> str:
        """``obsidian create name=<name> template=<template> path=<folder>``"""
        result = await self._run(
            "create", f"name={name}", f"template={template}", f"path={folder}",
        )
        return result.stdout or f"Created '{name}' from template '{template}'."
