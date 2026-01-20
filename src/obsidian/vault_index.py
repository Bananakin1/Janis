"""Wrapper around obsidiantools for vault indexing."""

from pathlib import Path
from typing import Optional

from obsidiantools.api import Vault


class VaultIndex:
    """In-memory index of an Obsidian vault using obsidiantools."""

    def __init__(self, vault_path: Path) -> None:
        """Initialize the vault index.

        Args:
            vault_path: Path to the Obsidian vault directory.
        """
        self._vault_path = vault_path
        self._vault: Optional[Vault] = None

    def refresh(self) -> None:
        """Rebuild the in-memory index from the vault filesystem."""
        self._vault = Vault(self._vault_path).connect()

    @property
    def vault(self) -> Vault:
        """Get the vault instance, refreshing if needed."""
        if self._vault is None:
            self.refresh()
        return self._vault

    def note_exists(self, note_name: str) -> bool:
        """Check if a note exists in the vault.

        Args:
            note_name: Name of the note (without .md extension).

        Returns:
            True if the note exists, False otherwise.
        """
        return note_name in self.vault.md_file_index

    def search_notes(self, query: str) -> list[str]:
        """Search for notes by name using fuzzy matching.

        Args:
            query: Search query string.

        Returns:
            List of matching note names.
        """
        query_lower = query.lower()
        matches = []
        for note_name in self.vault.md_file_index:
            if query_lower in note_name.lower():
                matches.append(note_name)
        return sorted(matches)

    def get_backlinks(self, note_name: str) -> list[str]:
        """Get notes that link to the specified note.

        Args:
            note_name: Name of the note to find backlinks for.

        Returns:
            List of note names that link to the specified note.
        """
        backlinks = self.vault.get_backlinks(note_name)
        if backlinks is None:
            return []
        return list(backlinks)

    def get_note_path(self, note_name: str) -> Optional[Path]:
        """Get the filesystem path for a note.

        Args:
            note_name: Name of the note.

        Returns:
            Path to the note file, or None if not found.
        """
        if note_name not in self.vault.md_file_index:
            return None
        return self.vault.md_file_index[note_name]

    def get_all_notes(self) -> list[str]:
        """Get all note names in the vault.

        Returns:
            List of all note names.
        """
        return list(self.vault.md_file_index.keys())

    def get_vault_summary(self) -> dict:
        """Get summary statistics about the vault.

        Returns:
            Dictionary with vault statistics.
        """
        notes = self.get_all_notes()
        folders = set()
        for note_name in notes:
            path = self.get_note_path(note_name)
            if path:
                rel_path = path.relative_to(self._vault_path)
                if len(rel_path.parts) > 1:
                    folders.add(rel_path.parts[0])

        return {
            "total_notes": len(notes),
            "folders": sorted(folders),
            "recent_notes": notes[:10] if notes else [],
        }
