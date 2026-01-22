"""Unit tests for vault index module."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.obsidian.vault_index import VaultIndex


@pytest.fixture
def mock_vault():
    """Create a mock Vault object."""
    vault = MagicMock()
    vault.md_file_index = {
        "Meeting Notes": Path("/vault/Meetings/Meeting Notes.md"),
        "Sarah Chen": Path("/vault/People/Sarah Chen.md"),
        "Sarah Miller": Path("/vault/People/Sarah Miller.md"),
        "Project Alpha": Path("/vault/Projects/Project Alpha.md"),
        "Quick Note": Path("/vault/Inbox/Quick Note.md"),
    }
    vault.get_backlinks.return_value = ["Meeting Notes", "Project Alpha"]
    return vault


@pytest.fixture
def mock_vault_with_hubs():
    """Create a mock Vault object with hub notes."""
    vault = MagicMock()
    vault.md_file_index = {
        "MEETINGS": Path("/vault/MEETINGS.md"),
        "CENTRING 2.0": Path("/vault/Centring/CENTRING 2.0.md"),
        "RECORDS": Path("/vault/RECORDS.md"),
        "Meeting Notes": Path("/vault/Meetings/Meeting Notes.md"),
        "Sarah Chen": Path("/vault/People/Sarah Chen.md"),
        "Quick Note": Path("/vault/Inbox/Quick Note.md"),
        "AI": Path("/vault/AI.md"),  # Two chars, should be hub
        "I": Path("/vault/I.md"),  # Single char, should NOT be hub
    }
    vault.get_backlinks.return_value = []
    return vault


@pytest.fixture
def vault_index_with_hubs(mock_vault_with_hubs):
    """Create a VaultIndex with mocked Vault containing hub notes."""
    with patch("src.obsidian.vault_index.Vault") as MockVault:
        instance = MockVault.return_value
        instance.connect.return_value = mock_vault_with_hubs

        index = VaultIndex(Path("/vault"))
        index.refresh()
        return index


@pytest.fixture
def vault_index(mock_vault):
    """Create a VaultIndex with mocked Vault."""
    with patch("src.obsidian.vault_index.Vault") as MockVault:
        instance = MockVault.return_value
        instance.connect.return_value = mock_vault

        index = VaultIndex(Path("/vault"))
        index.refresh()
        return index


class TestVaultIndexRefresh:
    """Tests for VaultIndex.refresh method."""

    def test_refresh_creates_vault(self):
        """Test that refresh creates and connects vault."""
        with patch("src.obsidian.vault_index.Vault") as MockVault:
            mock_instance = MagicMock()
            mock_instance.connect.return_value = mock_instance
            MockVault.return_value = mock_instance

            index = VaultIndex(Path("/test/vault"))
            index.refresh()

            MockVault.assert_called_once_with(Path("/test/vault"))
            mock_instance.connect.assert_called_once()


class TestVaultIndexNoteExists:
    """Tests for VaultIndex.note_exists method."""

    def test_note_exists_returns_true(self, vault_index):
        """Test note_exists returns True for existing note."""
        assert vault_index.note_exists("Sarah Chen") is True

    def test_note_exists_returns_false(self, vault_index):
        """Test note_exists returns False for non-existing note."""
        assert vault_index.note_exists("Unknown Note") is False


class TestVaultIndexSearchNotes:
    """Tests for VaultIndex.search_notes method."""

    def test_search_finds_exact_match(self, vault_index):
        """Test search finds exact match."""
        results = vault_index.search_notes("Sarah Chen")
        assert "Sarah Chen" in results

    def test_search_finds_partial_match(self, vault_index):
        """Test search finds partial matches."""
        results = vault_index.search_notes("Sarah")
        assert "Sarah Chen" in results
        assert "Sarah Miller" in results

    def test_search_case_insensitive(self, vault_index):
        """Test search is case insensitive."""
        results = vault_index.search_notes("sarah")
        assert "Sarah Chen" in results
        assert "Sarah Miller" in results

    def test_search_returns_sorted(self, vault_index):
        """Test search results are sorted."""
        results = vault_index.search_notes("Sarah")
        assert results == sorted(results)

    def test_search_no_matches(self, vault_index):
        """Test search with no matches returns empty list."""
        results = vault_index.search_notes("xyz123")
        assert results == []


class TestVaultIndexGetBacklinks:
    """Tests for VaultIndex.get_backlinks method."""

    def test_get_backlinks_returns_list(self, vault_index, mock_vault):
        """Test get_backlinks returns list of linking notes."""
        backlinks = vault_index.get_backlinks("Sarah Chen")
        assert backlinks == ["Meeting Notes", "Project Alpha"]

    def test_get_backlinks_none_returns_empty(self, vault_index, mock_vault):
        """Test get_backlinks returns empty list when None."""
        mock_vault.get_backlinks.return_value = None
        backlinks = vault_index.get_backlinks("Unknown")
        assert backlinks == []


class TestVaultIndexGetNotePath:
    """Tests for VaultIndex.get_note_path method."""

    def test_get_note_path_returns_path(self, vault_index):
        """Test get_note_path returns correct path."""
        path = vault_index.get_note_path("Sarah Chen")
        assert path == Path("/vault/People/Sarah Chen.md")

    def test_get_note_path_not_found(self, vault_index):
        """Test get_note_path returns None for missing note."""
        path = vault_index.get_note_path("Unknown Note")
        assert path is None


class TestVaultIndexGetAllNotes:
    """Tests for VaultIndex.get_all_notes method."""

    def test_get_all_notes_returns_list(self, vault_index):
        """Test get_all_notes returns all note names."""
        notes = vault_index.get_all_notes()
        assert len(notes) == 5
        assert "Sarah Chen" in notes
        assert "Meeting Notes" in notes


class TestVaultIndexGetVaultSummary:
    """Tests for VaultIndex.get_vault_summary method."""

    def test_summary_has_total_notes(self, vault_index):
        """Test summary includes total_notes."""
        summary = vault_index.get_vault_summary()
        assert summary["total_notes"] == 5

    def test_summary_has_folders(self, vault_index):
        """Test summary includes folders."""
        summary = vault_index.get_vault_summary()
        assert "folders" in summary
        assert isinstance(summary["folders"], list)

    def test_summary_has_recent_notes(self, vault_index):
        """Test summary includes recent_notes."""
        summary = vault_index.get_vault_summary()
        assert "recent_notes" in summary
        assert isinstance(summary["recent_notes"], list)


class TestVaultIndexGetHubNotes:
    """Tests for VaultIndex.get_hub_notes method."""

    def test_detects_all_caps_hub_notes(self, vault_index_with_hubs):
        """Test that ALL CAPS notes are detected as hubs."""
        hubs = vault_index_with_hubs.get_hub_notes()
        assert "MEETINGS" in hubs
        assert "RECORDS" in hubs

    def test_detects_all_caps_with_spaces(self, vault_index_with_hubs):
        """Test that ALL CAPS notes with spaces are detected."""
        hubs = vault_index_with_hubs.get_hub_notes()
        assert "CENTRING 2.0" in hubs

    def test_detects_short_all_caps(self, vault_index_with_hubs):
        """Test that short ALL CAPS notes (2+ chars) are detected."""
        hubs = vault_index_with_hubs.get_hub_notes()
        assert "AI" in hubs

    def test_ignores_single_char_caps(self, vault_index_with_hubs):
        """Test that single character notes are not detected as hubs."""
        hubs = vault_index_with_hubs.get_hub_notes()
        assert "I" not in hubs

    def test_excludes_mixed_case_notes(self, vault_index_with_hubs):
        """Test that mixed case notes are not detected as hubs."""
        hubs = vault_index_with_hubs.get_hub_notes()
        assert "Meeting Notes" not in hubs
        assert "Sarah Chen" not in hubs
        assert "Quick Note" not in hubs

    def test_returns_sorted_list(self, vault_index_with_hubs):
        """Test that hub notes are returned sorted."""
        hubs = vault_index_with_hubs.get_hub_notes()
        assert hubs == sorted(hubs)

    def test_empty_vault_returns_empty_list(self):
        """Test that empty vault returns empty hub list."""
        with patch("src.obsidian.vault_index.Vault") as MockVault:
            mock_vault = MagicMock()
            mock_vault.md_file_index = {}
            instance = MockVault.return_value
            instance.connect.return_value = mock_vault

            index = VaultIndex(Path("/vault"))
            index.refresh()

            hubs = index.get_hub_notes()
            assert hubs == []
