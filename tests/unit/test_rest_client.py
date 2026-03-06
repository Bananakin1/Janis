"""Unit tests for the expanded Obsidian REST client."""

import httpx
import pytest
from pytest_httpx import HTTPXMock

from src.backend.rest_client import ObsidianRESTClient, ValidationFailure


@pytest.fixture
def rest_client() -> ObsidianRESTClient:
    return ObsidianRESTClient("https://127.0.0.1:27124", "test-api-key")


class TestContextManager:
    @pytest.mark.asyncio
    async def test_creates_and_closes_client(self, rest_client):
        async with rest_client as client:
            assert client.client is not None
        assert rest_client._client is None


class TestReadAndWriteMethods:
    @pytest.mark.asyncio
    async def test_read_note_adds_markdown_extension(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(url="https://127.0.0.1:27124/vault/Test.md", text="content")

        async with rest_client as client:
            content = await client.read_note("Test")

        assert content == "content"
        assert httpx_mock.get_request().url.path == "/vault/Test.md"

    @pytest.mark.asyncio
    async def test_append_note_posts_markdown_body(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="https://127.0.0.1:27124/vault/Inbox/Test.md",
            status_code=204,
        )

        async with rest_client as client:
            assert await client.append_note("Inbox/Test", "new block") is True

        request = httpx_mock.get_request()
        assert request.method == "POST"
        assert request.content == b"new block"
        assert request.headers["Content-Type"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_patch_note_sends_target_headers(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="PATCH", status_code=200)

        async with rest_client as client:
            assert await client.patch_note(
                "Inbox/Test", "patched",
                target="## Current", target_type="heading", operation="replace",
            ) is True

        request = httpx_mock.get_request()
        assert request.method == "PATCH"
        assert request.headers["Target-Type"] == "heading"
        assert request.headers["Target"] == "## Current"
        assert request.headers["Operation"] == "replace"

    @pytest.mark.asyncio
    async def test_delete_note_returns_false_for_404(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="DELETE",
            url="https://127.0.0.1:27124/vault/Missing.md",
            status_code=404,
        )

        async with rest_client as client:
            assert await client.delete_note("Missing") is False

    @pytest.mark.asyncio
    async def test_open_note_posts_to_open_endpoint(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="https://127.0.0.1:27124/open/Inbox/Test.md",
            status_code=204,
        )

        async with rest_client as client:
            assert await client.open_note("Inbox/Test") is True

        assert httpx_mock.get_request().url.path == "/open/Inbox/Test.md"


class TestVaultListingAndDaily:
    @pytest.mark.asyncio
    async def test_list_vault_root(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url="https://127.0.0.1:27124/vault/",
            json=["04 Business", "05 Meetings"],
        )

        async with rest_client as client:
            result = await client.list_vault()

        assert result == ["04 Business", "05 Meetings"]

    @pytest.mark.asyncio
    async def test_list_vault_subdirectory(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="GET", status_code=200, json=["ITK.md", "Curinos.md"])

        async with rest_client as client:
            result = await client.list_vault("05 Meetings")

        assert result == ["ITK.md", "Curinos.md"]
        assert "05%20Meetings" in str(httpx_mock.get_request().url)

    @pytest.mark.asyncio
    async def test_read_daily_returns_none_for_404(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url="https://127.0.0.1:27124/periodic/daily/",
            status_code=404,
        )

        async with rest_client as client:
            assert await client.read_daily() is None

    @pytest.mark.asyncio
    async def test_append_daily_posts_markdown_body(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="https://127.0.0.1:27124/periodic/daily/",
            status_code=204,
        )

        async with rest_client as client:
            assert await client.append_daily("- follow up") is True

        request = httpx_mock.get_request()
        assert request.method == "POST"
        assert request.content == b"- follow up"


class TestSearchAndCommands:
    @pytest.mark.asyncio
    async def test_search_simple_uses_query_params(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", json=[{"filename": "Note.md"}], status_code=200)

        async with rest_client as client:
            result = await client.search_simple("Note", context_length=50)

        assert result == [{"filename": "Note.md"}]
        request = httpx_mock.get_request()
        assert request.url.path == "/search/simple/"
        assert "query=Note" in str(request.url)
        assert "contextLength=50" in str(request.url)

    @pytest.mark.asyncio
    async def test_search_alias_calls_simple_search(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(method="POST", json=[], status_code=200)

        async with rest_client as client:
            assert await client.search("foo") == []

    @pytest.mark.asyncio
    async def test_search_dql_returns_json_when_available(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="https://127.0.0.1:27124/search/",
            json=[{"path": "02 Specs/Test.md", "status": "in-progress"}],
            headers={"content-type": "application/json"},
        )

        async with rest_client as client:
            result = await client.search_dql('TABLE status FROM "02 Specs"')

        assert result == [{"path": "02 Specs/Test.md", "status": "in-progress"}]

    @pytest.mark.asyncio
    async def test_list_commands_returns_payload(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="GET",
            url="https://127.0.0.1:27124/commands/",
            json=[{"id": "workspace:new-tab"}],
        )

        async with rest_client as client:
            result = await client.list_commands()

        assert result == [{"id": "workspace:new-tab"}]

    @pytest.mark.asyncio
    async def test_execute_command_returns_text_when_not_json(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            method="POST",
            url="https://127.0.0.1:27124/commands/workspace%3Anew-tab",
            text="ok",
            headers={"content-type": "text/plain"},
        )

        async with rest_client as client:
            result = await client.execute_command("workspace:new-tab")

        assert result == "ok"


class TestValidationAndHealth:
    @pytest.mark.asyncio
    async def test_health_check_false_on_connection_error(self, rest_client, httpx_mock: HTTPXMock):
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        async with rest_client as client:
            assert await client.health_check() is False

    @pytest.mark.asyncio
    async def test_rejects_path_traversal(self, rest_client):
        async with rest_client as client:
            with pytest.raises(ValidationFailure):
                await client.read_note("../secrets")

    @pytest.mark.asyncio
    async def test_rejects_bodies_over_one_megabyte(self, rest_client):
        async with rest_client as client:
            with pytest.raises(ValidationFailure):
                await client.upsert_note("Inbox/Test", "x" * 1_000_001)
