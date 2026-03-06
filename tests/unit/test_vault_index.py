"""Unit tests for the vault index."""

from pathlib import Path

import pytest

from src.backend.vault_index import VaultIndex


@pytest.fixture
def temp_vault(tmp_path: Path) -> Path:
    (tmp_path / "05 Meetings").mkdir()
    (tmp_path / "02 Specs").mkdir()
    (tmp_path / "MEETINGS.md").write_text("# Hub\n", encoding="utf-8")
    (tmp_path / "05 Meetings" / "ITK.md").write_text(
        "[[Curinos]]\n",
        encoding="utf-8",
    )
    (tmp_path / "05 Meetings" / "Curinos.md").write_text(
        "[[ITK]]\n",
        encoding="utf-8",
    )
    (tmp_path / "02 Specs" / "SPEC-janis.md").write_text("# Spec\n", encoding="utf-8")
    return tmp_path


def test_refresh_indexes_files(temp_vault: Path):
    index = VaultIndex(temp_vault)
    index.refresh()
    assert set(index.get_all_notes()) >= {"ITK", "Curinos", "SPEC-janis", "MEETINGS"}


def test_search_notes_is_case_insensitive(temp_vault: Path):
    index = VaultIndex(temp_vault)
    index.refresh()
    assert index.search_notes("itk") == ["ITK"]


def test_get_note_path_returns_absolute_path(temp_vault: Path):
    index = VaultIndex(temp_vault)
    index.refresh()
    note_path = index.get_note_path("ITK")
    assert note_path == temp_vault / "05 Meetings" / "ITK.md"


def test_get_backlinks(temp_vault: Path):
    index = VaultIndex(temp_vault)
    index.refresh()
    backlinks = index.get_backlinks("ITK")
    assert "Curinos" in backlinks


def test_get_hub_notes(temp_vault: Path):
    index = VaultIndex(temp_vault)
    index.refresh()
    assert "MEETINGS" in index.get_hub_notes()


def test_get_vault_summary_has_counts(temp_vault: Path):
    index = VaultIndex(temp_vault)
    index.refresh()
    summary = index.get_vault_summary()
    assert summary["total_notes"] == 4
    assert "05 Meetings" in summary["folders"]
    assert summary["folder_counts"]["05 Meetings"] == 2
