"""Unit tests for the Obsidian CLI bridge."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.backend.cli_bridge import ObsidianCLI
from src.errors import BackendError, BackendUnavailableError


def _process(stdout: str = "", stderr: str = "", returncode: int = 0):
    process = MagicMock()
    process.communicate = AsyncMock(
        return_value=(stdout.encode("utf-8"), stderr.encode("utf-8"))
    )
    process.returncode = returncode
    return process


class TestObsidianCLI:
    @pytest.mark.asyncio
    async def test_move_sends_key_value_args(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian"), \
             patch("src.backend.cli_bridge.asyncio.create_subprocess_exec", return_value=_process(stdout="moved")) as create_proc:
            result = await cli.move("Inbox/A.md", "Archive/A.md")

        assert result == "moved"
        args = create_proc.call_args[0]
        assert args == ("obsidian", "move", "file=Inbox/A.md", "to=Archive/A.md")

    @pytest.mark.asyncio
    async def test_set_property_sends_key_value_args(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian"), \
             patch("src.backend.cli_bridge.asyncio.create_subprocess_exec", return_value=_process(stdout="done")) as create_proc:
            result = await cli.set_property("note.md", "status", "shipped")

        assert result == "done"
        args = create_proc.call_args[0]
        assert args == ("obsidian", "property:set", "name=status", "value=shipped", "file=note.md")

    @pytest.mark.asyncio
    async def test_set_property_raises_when_cli_missing(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value=None):
            with pytest.raises(BackendUnavailableError):
                await cli.set_property("note.md", "status", "shipped")

    @pytest.mark.asyncio
    async def test_list_tags_parses_json_dict(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian"), \
             patch(
                 "src.backend.cli_bridge.asyncio.create_subprocess_exec",
                 return_value=_process(stdout='{"#spec": 2, "#meeting": 5}'),
             ):
            result = await cli.list_tags()

        assert result == {"#meeting": 5, "#spec": 2}

    @pytest.mark.asyncio
    async def test_list_tags_parses_json_list(self):
        cli = ObsidianCLI("obsidian")
        payload = '[{"tag": "#spec", "count": 2}]'
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian"), \
             patch(
                 "src.backend.cli_bridge.asyncio.create_subprocess_exec",
                 return_value=_process(stdout=payload),
             ):
            result = await cli.list_tags()

        assert result == {"#spec": 2}

    @pytest.mark.asyncio
    async def test_get_backlinks_parses_json(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian"), \
             patch(
                 "src.backend.cli_bridge.asyncio.create_subprocess_exec",
                 return_value=_process(stdout='["A.md", "B.md"]'),
             ):
            result = await cli.get_backlinks("Target.md")

        assert result == ["A.md", "B.md"]

    @pytest.mark.asyncio
    async def test_get_backlinks_falls_back_to_lines(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian"), \
             patch(
                 "src.backend.cli_bridge.asyncio.create_subprocess_exec",
                 return_value=_process(stdout="A\nB\n"),
             ):
            result = await cli.get_backlinks("Target.md")

        assert result == ["A", "B"]

    @pytest.mark.asyncio
    async def test_raises_backend_error_on_non_zero_exit(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian"), \
             patch(
                 "src.backend.cli_bridge.asyncio.create_subprocess_exec",
                 return_value=_process(stderr="boom", returncode=1),
             ):
            with pytest.raises(BackendError):
                await cli.move("A.md", "B.md")

    @pytest.mark.asyncio
    async def test_is_available_caches_result(self):
        cli = ObsidianCLI("obsidian")
        with patch("src.backend.cli_bridge.shutil.which", return_value="/usr/bin/obsidian") as mock_which:
            assert cli.is_available() is True
            assert cli.is_available() is True
        assert mock_which.call_count == 1
