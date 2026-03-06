"""Agent orchestrator with provider-agnostic tool-calling loop."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Optional

from src.adapters.base import AgentRequest, AgentResponse
from src.agent.memory import MemoryStore
from src.agent.prompt_builder import PromptBuilder
from src.agent.providers.azure_openai import AzureOpenAIProvider
from src.backend.cli_bridge import ObsidianCLI
from src.backend.rest_client import ObsidianRESTClient
from src.backend.vault_index import VaultIndex
from src.config.settings import Settings
from src.errors import ProviderError
from src.tools.base import ToolContext, ToolResult
from src.tools.registry import ToolRegistry


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ConversationTurn:
    """Backward-compatible conversation turn type used by tests."""

    role: str
    author: str
    content: str


class Orchestrator:
    """Main agent orchestrator for processing requests through the tool loop."""

    def __init__(
        self,
        settings: Settings,
        *,
        provider=None,
        registry: ToolRegistry | None = None,
        memory: MemoryStore | None = None,
        prompt_builder: PromptBuilder | None = None,
        rest_client_cls=ObsidianRESTClient,
        cli: ObsidianCLI | None = None,
        vault_index: VaultIndex | None = None,
    ) -> None:
        self._settings = settings
        self._vault_index = vault_index or VaultIndex(settings.obsidian_vault_path)
        self._registry = registry or ToolRegistry.discover()
        self._memory = memory or MemoryStore(
            settings.memory_db_path,
            summary_interval=settings.memory_summary_interval,
        )
        self._prompt_builder = prompt_builder or PromptBuilder(
            settings,
            self._registry,
            cache_ttl_seconds=settings.prompt_cache_ttl_seconds,
        )
        self._rest_client_cls = rest_client_cls
        self._cli = cli or ObsidianCLI(settings.obsidian_cli_command)
        self._provider = provider
        self._provider_error: str | None = None
        self.last_agent_response: AgentResponse | None = None

        if self._provider is None:
            try:
                if settings.llm_provider != "azure_openai":
                    raise ProviderError(f"Unsupported LLM provider '{settings.llm_provider}'.")
                self._provider = AzureOpenAIProvider(settings)
            except Exception as exc:
                logger.error("Failed to initialize LLM provider: %s", exc)
                self._provider_error = str(exc)

    def _build_input_items(self, request: AgentRequest, system_prompt: str) -> list[dict]:
        items: list[dict] = [{"role": "system", "content": system_prompt}]
        summary = self._memory.get_latest_summary(request.user_id)
        if summary:
            items.append(
                {
                    "role": "system",
                    "content": f"Conversation summary for {request.user_name}: {summary}",
                }
            )
        for turn in self._memory.get_recent_messages(request.user_id):
            if turn.role == "user":
                items.append({"role": "user", "content": f"[{turn.author}]: {turn.content}"})
            else:
                items.append({"role": "assistant", "content": turn.content})
        items.append({"role": "user", "content": f"[{request.user_name}]: {request.message}"})
        return items

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        ctx: ToolContext,
    ) -> ToolResult:
        return await self._registry.execute(tool_name, arguments, ctx)

    async def _record_exchange(self, request: AgentRequest, response_text: str) -> None:
        self._memory.add_exchange(request.user_id, request.user_name, request.message, response_text)
        await self._memory.maybe_summarize(request.user_id, self._provider)

    async def process_request(self, request: AgentRequest) -> AgentResponse:
        await asyncio.to_thread(self._vault_index.refresh)

        async with self._rest_client_cls(
            self._settings.obsidian_api_url,
            self._settings.obsidian_api_key,
        ) as rest_client:
            if not await rest_client.health_check():
                response = AgentResponse(text="Obsidian is not running. Please open it and try again.")
                self.last_agent_response = response
                return response

            if self._provider is None:
                response = AgentResponse(
                    text=self._provider_error or "I'm having trouble connecting to the AI service."
                )
                self.last_agent_response = response
                return response

            base_ctx = ToolContext(
                settings=self._settings,
                rest=rest_client,
                cli=self._cli if self._cli.is_available() else None,
                vault_index=self._vault_index,
                request=request,
                memory=self._memory,
                state={},
            )
            system_prompt, tools = await self._prompt_builder.build(rest_client, self._vault_index, base_ctx)
            input_items = self._build_input_items(request, system_prompt)

            for _ in range(self._settings.max_tool_iterations):
                try:
                    provider_response = await self._provider.generate(input_items, tools=tools)
                except Exception:
                    logger.exception("Provider call failed")
                    response = AgentResponse(text="I'm having trouble connecting to the AI service.")
                    self.last_agent_response = response
                    return response
                if not provider_response.tool_calls:
                    text = provider_response.text or "I processed your request."
                    response = AgentResponse(text=text)
                    await self._record_exchange(request, text)
                    self.last_agent_response = response
                    return response

                input_items.extend(provider_response.raw_output_items)
                for tool_call in provider_response.tool_calls:
                    try:
                        arguments = json.loads(tool_call.arguments)
                        result = await self._execute_tool(tool_call.name, arguments, base_ctx)
                    except Exception as exc:
                        logger.exception("Tool execution failed for %s", tool_call.name)
                        result = ToolResult(content=f"Error executing {tool_call.name}: {exc}")

                    if result.stop:
                        response = result.response or AgentResponse(text=result.content)
                        await self._record_exchange(request, response.text)
                        self.last_agent_response = response
                        return response

                    input_items.append(
                        {
                            "type": "function_call_output",
                            "call_id": tool_call.call_id,
                            "output": result.content,
                        }
                    )

            input_items.append(
                {
                    "role": "user",
                    "content": "You have run out of tool calls. Summarize what you accomplished and what you could not complete.",
                }
            )
            try:
                provider_response = await self._provider.generate(input_items, tools=None)
            except Exception:
                logger.exception("Provider call failed while forcing final response")
                provider_response = None
            text = provider_response.text if provider_response is not None else "I'm having trouble connecting to the AI service."
            response = AgentResponse(text=text)
            await self._record_exchange(request, text)
            self.last_agent_response = response
            return response

    async def process_message(
        self,
        user_message: str,
        author: str = "User",
        user_id: str | None = None,
    ) -> str:
        request = AgentRequest(
            user_id=user_id or author,
            user_name=author,
            message=user_message,
        )
        response = await self.process_request(request)
        return response.text

    async def check_health(self) -> tuple[bool, Optional[str]]:
        async with self._rest_client_cls(
            self._settings.obsidian_api_url,
            self._settings.obsidian_api_key,
        ) as rest_client:
            if not await rest_client.health_check():
                return False, "Obsidian REST API is not available"
        return True, None
