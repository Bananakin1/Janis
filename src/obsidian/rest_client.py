"""Async HTTP client for Obsidian Local REST API."""

from typing import Optional
import httpx


class ObsidianRESTClient:
    """Async client for interacting with Obsidian Local REST API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        """Initialize the REST client.

        Args:
            base_url: Base URL of the Obsidian REST API (e.g., https://127.0.0.1:27124).
            api_key: API key for authentication.
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> "ObsidianRESTClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            verify=False,  # Self-signed cert for local REST API
            timeout=30.0,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get the HTTP client instance."""
        if self._client is None:
            raise RuntimeError(
                "Client not initialized. Use 'async with' context manager."
            )
        return self._client

    async def read_note(self, path: str) -> Optional[str]:
        """Read the content of a note.

        Args:
            path: Path to the note relative to vault root (e.g., "Inbox/My Note.md").

        Returns:
            Note content as string, or None if note doesn't exist.
        """
        # Ensure path has .md extension
        if not path.endswith(".md"):
            path = f"{path}.md"

        try:
            response = await self.client.get(
                f"/vault/{path}",
                headers={"Accept": "text/markdown"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise

    async def upsert_note(self, path: str, content: str) -> bool:
        """Create or update a note.

        Args:
            path: Path to the note relative to vault root (e.g., "Inbox/My Note.md").
            content: Markdown content to write.

        Returns:
            True if successful.
        """
        # Ensure path has .md extension
        if not path.endswith(".md"):
            path = f"{path}.md"

        response = await self.client.put(
            f"/vault/{path}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        response.raise_for_status()
        return True

    async def search(self, query: str, context_length: int = 100) -> list[dict]:
        """Search for notes using simple text search.

        Args:
            query: Search query string.
            context_length: Number of characters of context to return around matches.

        Returns:
            List of search results with filename and matches.
        """
        response = await self.client.post(
            "/search/simple/",
            params={"query": query, "contextLength": context_length},
        )
        response.raise_for_status()
        return response.json()

    async def health_check(self) -> bool:
        """Check if the Obsidian REST API is available.

        Returns:
            True if API is reachable, False otherwise.
        """
        try:
            response = await self.client.get("/")
            return response.status_code == 200
        except httpx.RequestError:
            return False
