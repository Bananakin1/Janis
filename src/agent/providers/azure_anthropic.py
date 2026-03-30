"""Azure Anthropic (AnthropicFoundry) provider for Claude models."""

from __future__ import annotations

import json
import logging
from typing import Any

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from src.agent.providers.base import LLMProvider, ProviderResponse, ToolCall
from src.errors import ProviderError

try:
    from anthropic import (
        APIConnectionError,
        APIStatusError,
        AsyncAnthropicFoundry,
        RateLimitError,
    )

    _HAS_ANTHROPIC = True
except ImportError:  # pragma: no cover
    _HAS_ANTHROPIC = False

logger = logging.getLogger(__name__)


def _is_transient_error(exception: BaseException) -> bool:
    if not _HAS_ANTHROPIC:
        return False
    if isinstance(exception, (APIConnectionError, RateLimitError)):
        return True
    if isinstance(exception, APIStatusError):
        return exception.status_code >= 500
    return False


_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=30, jitter=5),
    retry=retry_if_exception(_is_transient_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


def _merge_consecutive_user_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive user messages into single messages with combined content blocks."""
    if not messages:
        return messages

    merged: list[dict[str, Any]] = []
    for msg in messages:
        if merged and merged[-1]["role"] == "user" and msg["role"] == "user":
            prev_content = merged[-1]["content"]
            new_content = msg["content"]
            # Normalize both to list-of-blocks format
            if isinstance(prev_content, str):
                prev_content = [{"type": "text", "text": prev_content}]
            if isinstance(new_content, str):
                new_content = [{"type": "text", "text": new_content}]
            merged[-1]["content"] = prev_content + new_content
        else:
            merged.append(msg.copy())
    return merged


class AzureAnthropicProvider(LLMProvider):
    """Provider implementation backed by Azure-hosted Anthropic models via AnthropicFoundry."""

    def __init__(self, settings: Any) -> None:
        if not _HAS_ANTHROPIC:
            raise ProviderError("The Anthropic Python SDK is not installed.")

        self._settings = settings
        api_key = settings.azure_anthropic_api_key or settings.azure_openai_api_key
        if not api_key:
            raise ProviderError("No API key configured for Azure Anthropic provider.")

        endpoint = settings.azure_anthropic_endpoint
        if not endpoint:
            raise ProviderError("AZURE_ANTHROPIC_ENDPOINT is not configured.")

        self._model = settings.azure_anthropic_deployment

        self._client = AsyncAnthropicFoundry(
            api_key=api_key,
            base_url=endpoint.rstrip("/"),
        )

    def _extract_system_and_messages(
        self, input_items: list[dict[str, Any]]
    ) -> tuple[str, list[dict[str, Any]]]:
        """Split input items into a system string and Anthropic messages list."""
        system_parts: list[str] = []
        messages: list[dict[str, Any]] = []

        for item in input_items:
            role = item.get("role")
            item_type = item.get("type")

            if role == "system":
                system_parts.append(item["content"])
            elif role == "assistant":
                content = item.get("content")
                # Could be a string or a list of content blocks (raw_output_items)
                if isinstance(content, list):
                    messages.append({"role": "assistant", "content": content})
                else:
                    messages.append({"role": "assistant", "content": content})
            elif role == "user":
                content = item.get("content")
                if isinstance(content, list):
                    messages.append({"role": "user", "content": content})
                else:
                    messages.append({"role": "user", "content": content})
            elif item_type == "function_call_output":
                # OpenAI-format tool result from internal format — convert to Anthropic
                messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": item["call_id"],
                            "content": item["output"],
                        }
                    ],
                })

        return "\n\n".join(system_parts), messages

    @_llm_retry
    async def _create_message(self, **kwargs: Any) -> Any:
        async with self._client.messages.stream(**kwargs) as stream:
            return await stream.get_final_message()

    async def generate(
        self,
        input_items: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        system, messages = self._extract_system_and_messages(input_items)
        messages = _merge_consecutive_user_messages(messages)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 100_000,
            "system": system,
            "messages": messages,
            "thinking": {"type": "adaptive"},
        }
        if tools:
            kwargs["tools"] = tools

        try:
            response = await self._create_message(**kwargs)
        except Exception as exc:  # pragma: no cover
            raise ProviderError("I'm having trouble connecting to the AI service.") from exc

        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        raw_content_blocks: list[dict[str, Any]] = []

        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(
                    ToolCall(
                        call_id=block.id,
                        name=block.name,
                        arguments=json.dumps(block.input),
                    )
                )
                raw_content_blocks.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
            elif block.type == "thinking":
                # Preserve thinking blocks for re-injection (required by API)
                raw_content_blocks.append({
                    "type": "thinking",
                    "thinking": getattr(block, "thinking", ""),
                    "signature": getattr(block, "signature", ""),
                })
            elif block.type == "text":
                text_parts.append(block.text)
                raw_content_blocks.append({
                    "type": "text",
                    "text": block.text,
                })

        raw_output_items = [{"role": "assistant", "content": raw_content_blocks}]

        return ProviderResponse(
            text="\n".join(text_parts),
            tool_calls=tool_calls,
            raw_output_items=raw_output_items,
        )

    def format_tool_result(self, tool_call: Any, output: str) -> dict[str, Any]:
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_call.call_id,
                    "content": output,
                }
            ],
        }

    def format_tool_schemas(self, schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted = []
        for schema in schemas:
            converted.append({
                "name": schema["name"],
                "description": schema["description"],
                "input_schema": schema["parameters"],
            })
        return converted

    async def summarize(self, conversation_text: str) -> str:
        prompt = (
            "Summarize the following Janis conversation for long-term memory. "
            "Preserve referenced notes, people, folders, and unresolved intent in under 120 words.\n\n"
            f"{conversation_text}"
        )
        response = await self.generate(
            [{"role": "user", "content": prompt}],
            tools=None,
        )
        return response.text.strip()
