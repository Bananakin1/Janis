"""Vault indexing with `obsidiantools` fallback support."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from obsidiantools.api import Vault as ObsidianToolsVault
except ImportError:  # pragma: no cover - exercised only when dependency missing
    ObsidianToolsVault = None


WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(slots=True)
class _FilesystemVault:
    """Minimal vault adapter used when obsidiantools is unavailable."""

    root: Path
    md_file_index: dict[str, Path]
    _backlinks: dict[str, set[str]]

    @classmethod
    def build(cls, root: Path) -> "_FilesystemVault":
        md_file_index: dict[str, Path] = {}
        backlinks: dict[str, set[str]] = {}
        for file_path in sorted(root.rglob("*.md")):
            note_name = file_path.stem
            relative_path = file_path.relative_to(root)
            md_file_index[note_name] = relative_path
            content = file_path.read_text(encoding="utf-8")
            for match in WIKILINK_RE.findall(content):
                target = match.split("|", 1)[0].split("#", 1)[0].split("/")[-1].strip()
                if target:
                    backlinks.setdefault(target, set()).add(note_name)
        return cls(root=root, md_file_index=md_file_index, _backlinks=backlinks)

    def get_backlinks(self, note_name: str) -> list[str]:
        return sorted(self._backlinks.get(note_name, set()))


class VaultIndex:
    """In-memory index of an Obsidian vault."""

    def __init__(self, vault_path: Path) -> None:
        self._vault_path = Path(vault_path)
        self._vault: Any | None = None

    @property
    def vault_path(self) -> Path:
        return self._vault_path

    def refresh(self) -> None:
        if ObsidianToolsVault is not None:
            self._vault = ObsidianToolsVault(self._vault_path).connect()
        else:  # pragma: no cover - fallback path used only without dependency
            self._vault = _FilesystemVault.build(self._vault_path)

    @property
    def vault(self) -> Any:
        if self._vault is None:
            self.refresh()
        return self._vault

    def note_exists(self, note_name: str) -> bool:
        return note_name in self.vault.md_file_index

    def search_notes(self, query: str) -> list[str]:
        query_lower = query.lower()
        return sorted(
            note_name
            for note_name in self.vault.md_file_index
            if query_lower in note_name.lower()
        )

    def get_backlinks(self, note_name: str) -> list[str]:
        backlinks = self.vault.get_backlinks(note_name)
        if backlinks is None:
            return []
        if isinstance(backlinks, set):
            return sorted(backlinks)
        return list(backlinks)

    def get_note_path(self, note_name: str) -> Path | None:
        path = self.vault.md_file_index.get(note_name)
        if path is None:
            return None
        path = Path(path)
        if path.is_absolute():
            return path
        return self._vault_path / path

    def get_all_notes(self) -> list[str]:
        return list(self.vault.md_file_index.keys())

    def get_hub_notes(self) -> list[str]:
        hubs = []
        for note_name in self.vault.md_file_index:
            name_no_spaces = note_name.replace(" ", "").replace(".", "")
            if name_no_spaces.isupper() and len(name_no_spaces) > 1:
                hubs.append(note_name)
        return sorted(hubs)

    def get_recent_notes(self, limit: int = 10) -> list[str]:
        notes = []
        for note_name, path in self.vault.md_file_index.items():
            note_path = Path(path)
            if not note_path.is_absolute():
                note_path = self._vault_path / note_path
            try:
                notes.append((note_path.stat().st_mtime, note_name))
            except FileNotFoundError:
                continue
        notes.sort(reverse=True)
        return [note_name for _, note_name in notes[:limit]]

    def get_folders(self) -> list[str]:
        folders = set()
        for path in self.vault.md_file_index.values():
            note_path = Path(path)
            if note_path.is_absolute():
                try:
                    note_path = note_path.relative_to(self._vault_path)
                except ValueError:
                    pass
            if len(note_path.parts) > 1:
                folders.add(note_path.parts[0])
        return sorted(folders)

    def list_directory(self, path: str | None = None) -> list[str]:
        base = self._vault_path
        if path:
            base = base / path
        if not base.exists() or not base.is_dir():
            return []
        return sorted(item.name for item in base.iterdir() if not item.name.startswith("."))

    def get_vault_summary(self) -> dict[str, Any]:
        notes = self.get_all_notes()
        folders = self.get_folders()
        counts: dict[str, int] = {}
        for note_name in notes:
            note_path = self.get_note_path(note_name)
            if note_path is None:
                continue
            try:
                relative = note_path.relative_to(self._vault_path)
            except ValueError:
                relative = note_path
            folder = relative.parts[0] if len(relative.parts) > 1 else ""
            counts[folder] = counts.get(folder, 0) + 1
        return {
            "total_notes": len(notes),
            "folders": folders,
            "folder_counts": counts,
            "recent_notes": self.get_recent_notes(),
        }
