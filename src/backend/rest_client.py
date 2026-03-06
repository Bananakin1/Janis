"""Async HTTP client for the Obsidian Local REST API."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.errors import BackendError, ValidationFailure


logger = logging.getLogger(__name__)

ALLOWED_PATH_RE = re.compile(r"^[a-zA-Z0-9 _./-]+$")
MAX_REST_BODY_BYTES = 1_000_000

_rest_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.25, max=10, jitter=2),
    retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def validate_vault_path(path: str) -> str:
    """Validate and normalize a vault-relative note or directory path."""
    normalized = path.strip().replace("\\", "/").strip("/")
    if not normalized:
        return ""
    if "\x00" in normalized:
        raise ValidationFailure("Vault path cannot contain null bytes.")
    parts = [part for part in normalized.split("/") if part]
    if any(part == ".." for part in parts):
        raise ValidationFailure("Vault path cannot traverse parent directories.")
    if not ALLOWED_PATH_RE.fullmatch(normalized):
        raise ValidationFailure("Vault path contains unsupported characters.")
    return "/".join(parts)


def ensure_markdown_path(path: str) -> str:
    """Ensure a vault path ends in `.md`."""
    normalized = validate_vault_path(path)
    if normalized.endswith(".md"):
        return normalized
    return f"{normalized}.md" if normalized else normalized


class ObsidianRESTClient:
    """Async client for interacting with Obsidian Local REST API."""

    def __init__(self, base_url: str, api_key: str, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "ObsidianRESTClient":
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
            verify=False,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")
        return self._client

    def _quote_path(self, path: str) -> str:
        return quote(path, safe="/")

    def _validate_content_size(self, content: str) -> None:
        if len(content.encode("utf-8")) > MAX_REST_BODY_BYTES:
            raise ValidationFailure("Request body exceeds the 1MB REST API limit.")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        expected_statuses: set[int] | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        response = await self.client.request(method, path, **kwargs)
        if expected_statuses and response.status_code in expected_statuses:
            return response
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "REST request failed: %s %s -> %s %s",
                method,
                exc.request.url,
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise BackendError(f"Obsidian REST API request failed for {exc.request.url.path}") from exc
        return response

    @_rest_retry
    async def read_note(self, path: str) -> str | None:
        note_path = ensure_markdown_path(path)
        response = await self._request(
            "GET",
            f"/vault/{self._quote_path(note_path)}",
            expected_statuses={404},
            headers={"Accept": "text/markdown"},
        )
        if response.status_code == 404:
            return None
        return response.text

    @_rest_retry
    async def upsert_note(self, path: str, content: str) -> bool:
        note_path = ensure_markdown_path(path)
        self._validate_content_size(content)
        await self._request(
            "PUT",
            f"/vault/{self._quote_path(note_path)}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return True

    @_rest_retry
    async def append_note(self, path: str, content: str) -> bool:
        note_path = ensure_markdown_path(path)
        self._validate_content_size(content)
        await self._request(
            "POST",
            f"/vault/{self._quote_path(note_path)}",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return True

    @_rest_retry
    async def patch_note(
        self,
        path: str,
        content: str,
        target: str | None = None,
        target_type: str | None = None,
        operation: str = "append",
    ) -> bool:
        """PATCH a note section.

        Args:
            path: Vault-relative note path.
            content: Content to apply.
            target: The specific heading, block ref, or frontmatter key.
            target_type: ``heading``, ``block``, or ``frontmatter``.
            operation: ``append``, ``prepend``, or ``replace``.
        """
        note_path = ensure_markdown_path(path)
        self._validate_content_size(content)
        headers: dict[str, str] = {"Content-Type": "text/markdown", "Operation": operation}
        if target_type:
            headers["Target-Type"] = target_type
        if target:
            headers["Target"] = target
        await self._request(
            "PATCH",
            f"/vault/{self._quote_path(note_path)}",
            content=content,
            headers=headers,
        )
        return True

    @_rest_retry
    async def delete_note(self, path: str) -> bool:
        note_path = ensure_markdown_path(path)
        response = await self._request(
            "DELETE",
            f"/vault/{self._quote_path(note_path)}",
            expected_statuses={200, 202, 204, 404},
        )
        return response.status_code != 404

    @_rest_retry
    async def list_vault(self, path: str | None = None) -> list[str]:
        normalized = validate_vault_path(path or "")
        endpoint = "/vault/"
        if normalized:
            endpoint = f"/vault/{self._quote_path(normalized)}/"
        response = await self._request(
            "GET",
            endpoint,
            headers={"Accept": "application/json"},
        )
        payload = response.json()
        if isinstance(payload, list):
            return [str(item) for item in payload]
        if isinstance(payload, Mapping):
            items = payload.get("files") or payload.get("items") or payload.get("children") or []
            return [str(item) for item in items]
        raise BackendError("Unexpected payload returned from list_vault.")

    @_rest_retry
    async def read_daily(self) -> str | None:
        response = await self.client.get(
            "/periodic/daily/",
            headers={"Accept": "text/markdown"},
        )
        if response.status_code == 404:
            return None
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error("Could not read daily note: %s", exc.response.text[:500])
            raise BackendError("Could not read today's daily note.") from exc
        return response.text

    @_rest_retry
    async def append_daily(self, content: str) -> bool:
        self._validate_content_size(content)
        await self._request(
            "POST",
            "/periodic/daily/",
            content=content,
            headers={"Content-Type": "text/markdown"},
        )
        return True

    @_rest_retry
    async def search_simple(self, query: str, context_length: int = 100) -> list[dict[str, Any]]:
        response = await self._request(
            "POST",
            "/search/simple/",
            params={"query": query, "contextLength": context_length},
        )
        payload = response.json()
        if not isinstance(payload, list):
            raise BackendError("Unexpected payload returned from simple search.")
        return [dict(item) for item in payload]

    async def search(self, query: str, context_length: int = 100) -> list[dict[str, Any]]:
        """Backward-compatible alias for simple search."""
        return await self.search_simple(query, context_length=context_length)

    @_rest_retry
    async def search_dql(self, query: str) -> list[dict[str, Any]] | dict[str, Any] | str:
        response = await self._request(
            "POST",
            "/search/",
            content=query,
            headers={"Content-Type": "text/plain"},
        )
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    @_rest_retry
    async def list_commands(self) -> list[dict[str, Any]]:
        response = await self._request("GET", "/commands/")
        payload = response.json()
        if not isinstance(payload, list):
            raise BackendError("Unexpected payload returned from list_commands.")
        return [dict(item) for item in payload]

    @_rest_retry
    async def execute_command(self, command_id: str) -> dict[str, Any] | str:
        response = await self._request("POST", f"/commands/{quote(command_id, safe='')}")
        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        return response.text

    @_rest_retry
    async def open_note(self, path: str) -> bool:
        note_path = ensure_markdown_path(path)
        await self._request("POST", f"/open/{self._quote_path(note_path)}")
        return True

    async def health_check(self) -> bool:
        try:
            response = await self.client.get("/")
            return response.status_code == 200
        except httpx.RequestError:
            return False
