"""Unit tests for REST client module."""

import pytest
import httpx
from pytest_httpx import HTTPXMock

from src.obsidian.rest_client import ObsidianRESTClient


@pytest.fixture
def rest_client():
    """Create a REST client for testing."""
    return ObsidianRESTClient(
        base_url="https://127.0.0.1:27124",
        api_key="test-api-key",
    )


class TestObsidianRESTClientInit:
    """Tests for ObsidianRESTClient initialization."""

    def test_init_stores_base_url(self):
        """Test that base_url is stored correctly."""
        client = ObsidianRESTClient("https://localhost:27124", "key")
        assert client._base_url == "https://localhost:27124"

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from base_url."""
        client = ObsidianRESTClient("https://localhost:27124/", "key")
        assert client._base_url == "https://localhost:27124"

    def test_init_stores_api_key(self):
        """Test that api_key is stored correctly."""
        client = ObsidianRESTClient("https://localhost:27124", "my-key")
        assert client._api_key == "my-key"


class TestObsidianRESTClientContextManager:
    """Tests for async context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_client(self, rest_client):
        """Test that context manager creates httpx client."""
        async with rest_client as client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

    @pytest.mark.asyncio
    async def test_context_manager_closes_client(self, rest_client):
        """Test that context manager closes httpx client on exit."""
        async with rest_client:
            pass
        assert rest_client._client is None

    @pytest.mark.asyncio
    async def test_client_property_outside_context_raises(self, rest_client):
        """Test that accessing client outside context raises error."""
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = rest_client.client


class TestObsidianRESTClientReadNote:
    """Tests for read_note method."""

    @pytest.mark.asyncio
    async def test_read_note_success(self, rest_client, httpx_mock: HTTPXMock):
        """Test successful note read."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Inbox/Test.md",
            text="# Test Note\n\nContent here.",
        )

        async with rest_client as client:
            content = await client.read_note("Inbox/Test")
            assert content == "# Test Note\n\nContent here."

    @pytest.mark.asyncio
    async def test_read_note_adds_md_extension(self, rest_client, httpx_mock: HTTPXMock):
        """Test that .md extension is added if missing."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Test.md",
            text="Content",
        )

        async with rest_client as client:
            await client.read_note("Test")

        request = httpx_mock.get_request()
        assert request.url.path == "/vault/Test.md"

    @pytest.mark.asyncio
    async def test_read_note_not_found(self, rest_client, httpx_mock: HTTPXMock):
        """Test read_note returns None for 404."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Missing.md",
            status_code=404,
        )

        async with rest_client as client:
            content = await client.read_note("Missing")
            assert content is None


class TestObsidianRESTClientUpsertNote:
    """Tests for upsert_note method."""

    @pytest.mark.asyncio
    async def test_upsert_note_success(self, rest_client, httpx_mock: HTTPXMock):
        """Test successful note upsert."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Inbox/New.md",
            method="PUT",
            status_code=200,
        )

        async with rest_client as client:
            result = await client.upsert_note("Inbox/New", "# Content")
            assert result is True

    @pytest.mark.asyncio
    async def test_upsert_note_adds_md_extension(self, rest_client, httpx_mock: HTTPXMock):
        """Test that .md extension is added if missing."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Test.md",
            method="PUT",
            status_code=200,
        )

        async with rest_client as client:
            await client.upsert_note("Test", "Content")

        request = httpx_mock.get_request()
        assert request.url.path == "/vault/Test.md"

    @pytest.mark.asyncio
    async def test_upsert_note_sends_content(self, rest_client, httpx_mock: HTTPXMock):
        """Test that content is sent in request body."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Test.md",
            method="PUT",
            status_code=200,
        )

        async with rest_client as client:
            await client.upsert_note("Test", "# My Content\n\nBody here.")

        request = httpx_mock.get_request()
        assert request.content == b"# My Content\n\nBody here."


class TestObsidianRESTClientSearch:
    """Tests for search method."""

    @pytest.mark.asyncio
    async def test_search_success(self, rest_client, httpx_mock: HTTPXMock):
        """Test successful search."""
        httpx_mock.add_response(
            method="POST",
            json=[{"filename": "Note1.md"}, {"filename": "Note2.md"}],
        )

        async with rest_client as client:
            results = await client.search("test query")
            assert len(results) == 2

        request = httpx_mock.get_request()
        assert request.url.path == "/search/simple/"
        assert "query=test+query" in str(request.url)
        assert "contextLength=100" in str(request.url)


class TestObsidianRESTClientHealthCheck:
    """Tests for health_check method."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, rest_client, httpx_mock: HTTPXMock):
        """Test health check returns True when API is available."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/",
            status_code=200,
        )

        async with rest_client as client:
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, rest_client, httpx_mock: HTTPXMock):
        """Test health check returns False on connection error."""
        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        async with rest_client as client:
            result = await client.health_check()
            assert result is False
