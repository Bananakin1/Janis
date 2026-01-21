"""Integration tests for ObsidianRESTClient HTTP flow."""

import pytest
from pytest_httpx import HTTPXMock

from src.obsidian.rest_client import ObsidianRESTClient


class TestRESTClientHTTPFlow:
    """Integration tests for REST client HTTP request/response flow."""

    @pytest.fixture
    def client(self):
        """Create a REST client for testing."""
        return ObsidianRESTClient(
            base_url="https://127.0.0.1:27124",
            api_key="test-api-key",
        )

    @pytest.mark.asyncio
    async def test_read_note_full_flow(self, client, httpx_mock: HTTPXMock):
        """Test complete read note flow including headers and response parsing."""
        note_content = """---
title: Test Note
type: general
---

# Test Note

This is the content.
"""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Inbox/Test%20Note.md",
            text=note_content,
            status_code=200,
        )

        async with client:
            result = await client.read_note("Inbox/Test Note")

        # Verify response
        assert result == note_content

        # Verify request details
        request = httpx_mock.get_request()
        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer test-api-key"
        assert request.headers["Accept"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_upsert_note_creates_new(self, client, httpx_mock: HTTPXMock):
        """Test upsert creates a new note with correct request body."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Inbox/New%20Note.md",
            method="PUT",
            status_code=204,
        )

        content = """---
title: New Note
type: general
---

# New Note

Fresh content here.
"""

        async with client:
            result = await client.upsert_note("Inbox/New Note", content)

        # Verify success
        assert result is True

        # Verify request
        request = httpx_mock.get_request()
        assert request.method == "PUT"
        assert request.headers["Content-Type"] == "text/markdown"
        assert request.content.decode() == content

    @pytest.mark.asyncio
    async def test_upsert_note_overwrites_existing(self, client, httpx_mock: HTTPXMock):
        """Test upsert overwrites existing note content."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/People/Sarah%20Chen.md",
            method="PUT",
            status_code=204,
        )

        updated_content = "# Sarah Chen\n\nUpdated bio."

        async with client:
            result = await client.upsert_note("People/Sarah Chen", updated_content)

        assert result is True

    @pytest.mark.asyncio
    async def test_search_with_results(self, client, httpx_mock: HTTPXMock):
        """Test search returns properly parsed results."""
        search_results = [
            {
                "filename": "Meetings/Team Standup.md",
                "matches": [
                    {"match": {"start": 100, "end": 110}, "context": "...discussed the project..."}
                ],
            },
            {
                "filename": "Projects/Project Alpha.md",
                "matches": [
                    {"match": {"start": 50, "end": 60}, "context": "...main project for Q1..."}
                ],
            },
        ]
        httpx_mock.add_response(
            method="POST",
            json=search_results,
            status_code=200,
        )

        async with client:
            results = await client.search("project")

        # Verify results parsed correctly
        assert len(results) == 2
        assert results[0]["filename"] == "Meetings/Team Standup.md"
        assert results[1]["filename"] == "Projects/Project Alpha.md"

        # Verify request used query params
        request = httpx_mock.get_request()
        assert request.method == "POST"
        assert "query=project" in str(request.url)
        assert "contextLength=100" in str(request.url)

    @pytest.mark.asyncio
    async def test_search_with_custom_context_length(self, client, httpx_mock: HTTPXMock):
        """Test search with custom context length parameter."""
        httpx_mock.add_response(
            method="POST",
            json=[],
            status_code=200,
        )

        async with client:
            await client.search("test", context_length=200)

        request = httpx_mock.get_request()
        assert "contextLength=200" in str(request.url)

    @pytest.mark.asyncio
    async def test_search_no_results(self, client, httpx_mock: HTTPXMock):
        """Test search with no matching results."""
        httpx_mock.add_response(
            method="POST",
            json=[],
            status_code=200,
        )

        async with client:
            results = await client.search("xyznonexistent")

        assert results == []

    @pytest.mark.asyncio
    async def test_read_note_not_found_returns_none(self, client, httpx_mock: HTTPXMock):
        """Test read note returns None for 404."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Missing.md",
            status_code=404,
            json={"errorCode": 40401, "message": "File not found"},
        )

        async with client:
            result = await client.read_note("Missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client, httpx_mock: HTTPXMock):
        """Test health check returns True when API responds."""
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/",
            status_code=200,
            json={"status": "OK", "versions": {"obsidian": "1.5.0", "self": "3.4.2"}},
        )

        async with client:
            is_healthy = await client.health_check()

        assert is_healthy is True

    @pytest.mark.asyncio
    async def test_health_check_unhealthy(self, client, httpx_mock: HTTPXMock):
        """Test health check returns False on connection error."""
        import httpx

        httpx_mock.add_exception(httpx.ConnectError("Connection refused"))

        async with client:
            is_healthy = await client.health_check()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_multiple_operations_in_sequence(self, client, httpx_mock: HTTPXMock):
        """Test multiple operations work correctly in sequence."""
        # Mock health check
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/",
            status_code=200,
        )

        # Mock read
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Inbox/Note.md",
            method="GET",
            text="# Old Content",
            status_code=200,
        )

        # Mock write
        httpx_mock.add_response(
            url="https://127.0.0.1:27124/vault/Inbox/Note.md",
            method="PUT",
            status_code=204,
        )

        async with client:
            # Health check
            healthy = await client.health_check()
            assert healthy is True

            # Read existing
            content = await client.read_note("Inbox/Note")
            assert content == "# Old Content"

            # Update
            success = await client.upsert_note("Inbox/Note", "# New Content")
            assert success is True

    @pytest.mark.asyncio
    async def test_authorization_header_sent_on_all_requests(
        self, client, httpx_mock: HTTPXMock
    ):
        """Test that authorization header is sent on all requests."""
        httpx_mock.add_response(status_code=200, text="content")
        httpx_mock.add_response(status_code=204)
        httpx_mock.add_response(status_code=200, json=[])

        async with client:
            await client.read_note("test")
            await client.upsert_note("test", "content")
            await client.search("query")

        requests = httpx_mock.get_requests()
        for request in requests:
            assert request.headers["Authorization"] == "Bearer test-api-key"

    @pytest.mark.asyncio
    async def test_path_with_special_characters(self, client, httpx_mock: HTTPXMock):
        """Test handling of paths with special characters."""
        httpx_mock.add_response(
            method="GET",
            text="# Content",
            status_code=200,
        )

        async with client:
            # Note name with spaces and special chars
            await client.read_note("Meetings/2024-01-15 Team Standup")

        request = httpx_mock.get_request()
        # URL should be properly encoded
        assert "/vault/Meetings/2024-01-15%20Team%20Standup.md" in str(request.url)
