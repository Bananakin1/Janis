"""Azure OpenAI Responses API provider."""

from __future__ import annotations

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
    from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
except ImportError:  # pragma: no cover - exercised only when dependency missing
    APIConnectionError = RateLimitError = APIStatusError = AsyncOpenAI = None


logger = logging.getLogger(__name__)


def _is_transient_error(exception: BaseException) -> bool:
    if APIConnectionError is not None and isinstance(exception, (APIConnectionError, RateLimitError)):
        return True
    if APIStatusError is not None and isinstance(exception, APIStatusError):
        return exception.status_code >= 500
    return False


_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=30, jitter=5),
    retry=retry_if_exception(_is_transient_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)


class AzureOpenAIProvider(LLMProvider):
    """Provider implementation backed by Azure OpenAI Responses API."""

    def __init__(self, settings: Any) -> None:
        if AsyncOpenAI is None:
            raise ProviderError("The OpenAI Python SDK is not installed.")
        self._settings = settings
        self._client = AsyncOpenAI(
            api_key=settings.azure_openai_api_key,
            base_url=f"{settings.azure_openai_endpoint.rstrip('/')}/openai/v1/",
        )

    @_llm_retry
    async def _create_response(self, **kwargs: Any) -> Any:
        return await self._client.responses.create(**kwargs)

    async def generate(
        self,
        input_items: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        kwargs: dict[str, Any] = {
            "model": self._settings.azure_openai_deployment,
            "input": input_items,
            "max_output_tokens": 4096,
            "store": False,
            "reasoning": {"effort": self._settings.reasoning_effort},
            "include": ["reasoning.encrypted_content"],
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["parallel_tool_calls"] = False

        try:
            response = await self._create_response(**kwargs)
        except Exception as exc:  # pragma: no cover - provider tests should mock
            raise ProviderError("I'm having trouble connecting to the AI service.") from exc

        tool_calls: list[ToolCall] = []
        raw_output_items: list[dict[str, Any]] = []
        for item in getattr(response, "output", []):
            item_type = getattr(item, "type", None)
            if item_type == "function_call":
                tool_calls.append(
                    ToolCall(
                        call_id=item.call_id,
                        name=item.name,
                        arguments=item.arguments,
                    )
                )
                raw_output_items.append(item.model_dump(exclude={"status"}))
            elif item_type == "reasoning" and getattr(item, "encrypted_content", None):
                raw_output_items.append(item.model_dump(exclude={"status"}))

        return ProviderResponse(
            text=getattr(response, "output_text", "") or "",
            tool_calls=tool_calls,
            raw_output_items=raw_output_items,
        )

    def format_tool_result(self, tool_call: Any, output: str) -> dict[str, Any]:
        return {
            "type": "function_call_output",
            "call_id": tool_call.call_id,
            "output": output,
        }

    def format_tool_schemas(self, schemas: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return schemas

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
