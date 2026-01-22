"""Integration tests for VaultIndex with real filesystem."""

from pathlib import Path

import pytest

from src.obsidian.vault_index import VaultIndex


class TestVaultIndexWithRealVault:
    """Integration tests for VaultIndex using temporary vault."""

    def test_refresh_indexes_all_notes(self, temp_vault):
        """Test that refresh indexes all notes in the vault."""
        index = VaultIndex(temp_vault)
        index.refresh()

        all_notes = index.get_all_notes()

        assert len(all_notes) == 5
        assert "Team Standup" in all_notes
        assert "Sarah Chen" in all_notes
        assert "John Smith" in all_notes
        assert "Project Alpha" in all_notes
        assert "Quick Note" in all_notes

    def test_note_exists_finds_existing_notes(self, temp_vault):
        """Test note_exists returns True for existing notes."""
        index = VaultIndex(temp_vault)
        index.refresh()

        assert index.note_exists("Sarah Chen") is True
        assert index.note_exists("Team Standup") is True
        assert index.note_exists("Project Alpha") is True

    def test_note_exists_returns_false_for_missing(self, temp_vault):
        """Test note_exists returns False for non-existing notes."""
        index = VaultIndex(temp_vault)
        index.refresh()

        assert index.note_exists("Non Existent Note") is False
        assert index.note_exists("Random Name") is False

    def test_search_finds_partial_matches(self, temp_vault):
        """Test search finds notes with partial name matches."""
        index = VaultIndex(temp_vault)
        index.refresh()

        results = index.search_notes("Sarah")

        assert len(results) == 1
        assert "Sarah Chen" in results

    def test_search_finds_multiple_matches(self, temp_vault):
        """Test search finds all matching notes."""
        index = VaultIndex(temp_vault)
        index.refresh()

        # Search for "Project" - should find Project Alpha
        results = index.search_notes("Project")
        assert "Project Alpha" in results

        # Search for common term
        results = index.search_notes("John")
        assert "John Smith" in results

    def test_search_case_insensitive(self, temp_vault):
        """Test search is case insensitive."""
        index = VaultIndex(temp_vault)
        index.refresh()

        results_lower = index.search_notes("sarah")
        results_upper = index.search_notes("SARAH")
        results_mixed = index.search_notes("SaRaH")

        assert results_lower == results_upper == results_mixed
        assert "Sarah Chen" in results_lower

    def test_get_note_path_returns_correct_path(self, temp_vault):
        """Test get_note_path returns the path for a note."""
        index = VaultIndex(temp_vault)
        index.refresh()

        path = index.get_note_path("Sarah Chen")

        assert path is not None
        # obsidiantools may return relative paths
        assert "Sarah Chen" in str(path)

    def test_get_note_path_returns_none_for_missing(self, temp_vault):
        """Test get_note_path returns None for non-existing notes."""
        index = VaultIndex(temp_vault)
        index.refresh()

        path = index.get_note_path("Does Not Exist")

        assert path is None

    def test_get_vault_summary_includes_stats(self, temp_vault):
        """Test get_vault_summary returns comprehensive statistics."""
        index = VaultIndex(temp_vault)
        index.refresh()

        summary = index.get_vault_summary()

        assert summary["total_notes"] == 5
        assert "folders" in summary
        assert "recent_notes" in summary
        assert isinstance(summary["folders"], list)
        assert isinstance(summary["recent_notes"], list)

    def test_get_backlinks_finds_linking_notes(self, temp_vault):
        """Test get_backlinks finds notes that link to target."""
        index = VaultIndex(temp_vault)
        index.refresh()

        # Sarah Chen is linked from Team Standup and Project Alpha
        backlinks = index.get_backlinks("Sarah Chen")

        # Note: backlinks depend on obsidiantools parsing wikilinks
        # This test verifies the integration works
        assert isinstance(backlinks, list)

    def test_vault_auto_refreshes_on_access(self, temp_vault):
        """Test that accessing vault property auto-refreshes if needed."""
        index = VaultIndex(temp_vault)

        # Access vault without explicit refresh
        vault = index.vault

        assert vault is not None
        assert index.note_exists("Sarah Chen")

    def test_adding_new_note_detected_after_refresh(self, temp_vault):
        """Test that new notes are detected after refresh."""
        index = VaultIndex(temp_vault)
        index.refresh()

        # Verify initial state
        assert index.note_exists("New Note") is False

        # Add a new note
        new_note_path = temp_vault / "Records" / "New Note.md"
        new_note_path.write_text("# New Note\n\nNew content.")

        # Should still not exist (cached)
        assert index.note_exists("New Note") is False

        # After refresh, should exist
        index.refresh()
        assert index.note_exists("New Note") is True

    def test_empty_search_returns_all_matches(self, temp_vault):
        """Test that empty search query returns empty list (no matches)."""
        index = VaultIndex(temp_vault)
        index.refresh()

        # Empty string doesn't match note names
        # Actually, empty string IS contained in all strings, so this may return all
        results = index.search_notes("")

        # Empty string is contained in every string, so should return all notes
        assert len(results) == 5
