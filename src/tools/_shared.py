"""Shared helpers for tool modules."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator

from src.backend.rest_client import ensure_markdown_path, validate_vault_path


DATE_HEADING_RE = re.compile(r"^## (\d{2}/\d{2}/\d{4})\s*$")


class ToolModel(BaseModel):
    """Common Pydantic configuration for tool argument models."""

    model_config = ConfigDict(extra="forbid")


class PathToolModel(ToolModel):
    """Base model for note or folder paths."""

    path: str

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return validate_vault_path(value)


def resolve_note_path(note_name_or_path: str, vault_index: Any) -> str:
    """Resolve a note name or path to a vault-relative markdown path."""
    normalized = note_name_or_path.strip()
    if "/" in normalized or normalized.endswith(".md"):
        return ensure_markdown_path(normalized)
    note_path = vault_index.get_note_path(normalized)
    if note_path is None:
        return ensure_markdown_path(normalized)
    note_path = Path(note_path)
    if note_path.is_absolute():
        note_path = note_path.relative_to(vault_index.vault_path)
    return ensure_markdown_path(note_path.as_posix())


def prepend_to_note(existing_content: str, new_content: str) -> str:
    """Insert a dated block before the first date heading."""
    lines = existing_content.split("\n")
    insert_idx: int | None = None

    for index, line in enumerate(lines):
        if DATE_HEADING_RE.match(line):
            insert_idx = index
            break

    new_block = new_content.strip()
    if insert_idx is not None:
        before_end = insert_idx
        while before_end > 0 and lines[before_end - 1].strip() == "":
            before_end -= 1
        before = "\n".join(lines[:before_end]).rstrip()
        after = "\n".join(lines[insert_idx:])
        if before:
            return f"{before}\n\n{new_block}\n\n{after}"
        return f"{new_block}\n\n{after}"

    trimmed = existing_content.rstrip()
    if trimmed:
        return f"{trimmed}\n\n{new_block}\n"
    return f"{new_block}\n"


def format_search_payload(payload: Any) -> str:
    """Format a search payload into concise plaintext."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        return json.dumps(payload, indent=2, sort_keys=True)
    if isinstance(payload, list):
        lines: list[str] = []
        for item in payload:
            if isinstance(item, dict):
                filename = item.get("filename") or item.get("path") or item.get("file") or "item"
                matches = item.get("matches") or []
                if matches:
                    context = str(matches[0].get("context", "")).strip()
                    lines.append(f"- {filename}: {context}")
                else:
                    lines.append(f"- {filename}")
            else:
                lines.append(f"- {item}")
        return "\n".join(lines)
    return str(payload)
