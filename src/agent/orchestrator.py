"""Agent orchestrator with tool-calling loop."""

import json
import logging
import re
from pathlib import Path
from typing import Optional

from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential_jitter,
    retry_if_exception,
    before_sleep_log,
)


logger = logging.getLogger(__name__)


def _is_transient_error(exception: BaseException) -> bool:
    """Check if an exception is a transient error worth retrying.

    Args:
        exception: The exception to check.

    Returns:
        True if the error is transient (should retry), False otherwise.
    """
    # Always retry connection errors and rate limits
    if isinstance(exception, (APIConnectionError, RateLimitError)):
        return True
    # Retry 5xx server errors, but not 4xx client errors (including 400 BadRequest)
    if isinstance(exception, APIStatusError):
        return exception.status_code >= 500
    return False


# Retry decorator for LLM API calls (transient errors only, not client errors like 400)
_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(initial=0.5, max=30, jitter=5),
    retry=retry_if_exception(_is_transient_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)

from src.config.settings import Settings
from src.obsidian.vault_index import VaultIndex
from src.obsidian.rest_client import ObsidianRESTClient
from src.agent.tools import (
    SearchNotesParams,
    ReadNoteParams,
    UpsertNoteParams,
    AskClarificationParams,
    get_tool_definitions,
)
from src.agent.prompts import build_system_prompt


# Characters to sanitize in note names
INVALID_CHARS = re.compile(r'[/\\:*?"<>|]')

MAX_TOOL_ITERATIONS = 8


class Orchestrator:
    """Main agent orchestrator for processing messages through Azure OpenAI Responses API."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the orchestrator.

        Args:
            settings: Application settings.
        """
        self._settings = settings
        self._vault_index = VaultIndex(settings.obsidian_vault_path)
        # Use base OpenAI client with Azure's v1 Responses API endpoint
        self._llm = AsyncOpenAI(
            api_key=settings.azure_openai_api_key,
            base_url=f"{settings.azure_openai_endpoint}/openai/v1/",
        )

    def _sanitize_note_name(self, name: str) -> str:
        """Sanitize a note name by replacing invalid characters.

        Args:
            name: Original note name.

        Returns:
            Sanitized note name.
        """
        return INVALID_CHARS.sub("-", name).strip()

    def _to_relative_path(self, path: Path) -> Path:
        """Convert path to be relative to vault root.

        obsidiantools may return absolute or relative paths. This normalizes to relative.

        Args:
            path: Path that may be absolute or relative.

        Returns:
            Path relative to vault root.
        """
        if path.is_absolute():
            return path.relative_to(self._settings.obsidian_vault_path)
        return path

    @_llm_retry
    async def _call_llm(
        self,
        input_items: list[dict],
        tools: list[dict] | None = None,
    ):
        """Call the LLM using Responses API with retry logic for transient failures.

        Args:
            input_items: Input items (messages and tool outputs).
            tools: Optional tool definitions.

        Returns:
            LLM response.
        """
        kwargs = {
            "model": self._settings.azure_openai_deployment,
            "input": input_items,
            "max_output_tokens": 4096,
            "reasoning": {
                "effort": self._settings.reasoning_effort,
            },
            "store": False,  # Stateless mode
            # Include encrypted reasoning for multi-turn context preservation
            "include": ["reasoning.encrypted_content"],
        }
        if tools:
            kwargs["tools"] = tools
            # Disable parallel tool calls for strict mode compatibility
            kwargs["parallel_tool_calls"] = False

        return await self._llm.responses.create(**kwargs)

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict,
        rest_client: ObsidianRESTClient,
    ) -> str:
        """Execute a tool and return the result.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            rest_client: Obsidian REST client instance.

        Returns:
            Tool execution result as string.
        """
        if tool_name == "search_notes":
            params = SearchNotesParams(**arguments)
            matches = self._vault_index.search_notes(params.query)
            if matches:
                return f"Found {len(matches)} notes: {', '.join(matches)}"
            return "No matching notes found."

        elif tool_name == "read_note":
            params = ReadNoteParams(**arguments)
            # Try to find the note path from vault index
            note_path = self._vault_index.get_note_path(params.note_name)
            if note_path:
                rel_path = self._to_relative_path(note_path)
                # Use forward slashes for REST API URLs regardless of OS
                content = await rest_client.read_note(rel_path.as_posix())
            else:
                # Try direct path
                content = await rest_client.read_note(params.note_name)

            if content:
                return content
            return f"Note '{params.note_name}' not found."

        elif tool_name == "upsert_note":
            params = UpsertNoteParams(**arguments)

            # First check if note already exists in vault index
            existing_path = self._vault_index.get_note_path(params.note_name)

            if existing_path:
                # Note exists - replace with full content provided by LLM
                rel_path = self._to_relative_path(existing_path)
                api_path = rel_path.with_suffix('').as_posix()  # REST client adds .md
                folder_name = rel_path.parent.as_posix()

                await rest_client.upsert_note(api_path, params.content)
                return f"Updated note '{params.note_name}' in {folder_name}/"

            # Note doesn't exist - create new with sanitized name
            note_name = self._sanitize_note_name(params.note_name)
            folder = params.folder or self._settings.default_note_folder
            path = f"{folder}/{note_name}"
            await rest_client.upsert_note(path, params.content)
            return f"Created note '{note_name}' in {folder}/"

        elif tool_name == "ask_clarification":
            params = AskClarificationParams(**arguments)
            matches_list = "\n".join(f"- {m}" for m in params.matches)
            return f"{params.question}\n\nMatches found:\n{matches_list}"

        return f"Unknown tool: {tool_name}"

    async def process_message(self, user_message: str) -> str:
        """Process a user message through the agent.

        Args:
            user_message: Natural language message from the user.

        Returns:
            Agent response string.
        """
        # Refresh vault index before processing
        self._vault_index.refresh()

        # Build system prompt with current vault context
        vault_summary = self._vault_index.get_vault_summary()
        hub_notes = self._vault_index.get_hub_notes()
        system_prompt = build_system_prompt(vault_summary, hub_notes)

        logger.info(f"Processing message: {user_message[:100]}{'...' if len(user_message) > 100 else ''}")
        logger.debug(f"Vault summary: {vault_summary}")

        # Responses API input format
        input_items = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        async with ObsidianRESTClient(
            self._settings.obsidian_api_url,
            self._settings.obsidian_api_key,
        ) as rest_client:
            # Check if Obsidian is available
            if not await rest_client.health_check():
                return "Obsidian is not running. Please open it and try again."

            # Tool-calling loop
            tools = get_tool_definitions()
            for iteration in range(MAX_TOOL_ITERATIONS):
                logger.debug(f"[Iteration {iteration + 1}/{MAX_TOOL_ITERATIONS}] Calling LLM...")

                response = await self._call_llm(input_items, tools)

                # Extract tool calls from response output
                tool_calls = [
                    item for item in response.output
                    if item.type == "function_call"
                ]

                # If no tool calls, return the response text
                if not tool_calls:
                    output_text = response.output_text or ""
                    logger.debug(f"[Iteration {iteration + 1}] No tool calls, final response: {output_text[:200] if output_text else 'None'}...")
                    return output_text or "I processed your request."

                # Log tool calls
                logger.info(f"[Iteration {iteration + 1}] LLM requested {len(tool_calls)} tool call(s)")

                # Add items to history for multi-turn context
                # - function_call: needed for tool execution tracking
                # - reasoning: preserve encrypted content for reasoning continuity (store=false)
                # Exclude 'status' field which is output-only and not accepted in input
                for item in response.output:
                    if item.type == "function_call":
                        input_items.append(item.model_dump(exclude={"status"}))
                    elif item.type == "reasoning" and getattr(item, "encrypted_content", None):
                        # Pass through reasoning with encrypted content for context preservation
                        input_items.append(item.model_dump(exclude={"status"}))

                # Execute each tool call and add results
                for tool_call in tool_calls:
                    try:
                        arguments = json.loads(tool_call.arguments)
                        logger.info(f"  -> {tool_call.name}({json.dumps(arguments, indent=2)})")

                        result = await self._execute_tool(
                            tool_call.name,
                            arguments,
                            rest_client,
                        )
                        logger.info(f"  <- Result: {result[:200]}{'...' if len(result) > 200 else ''}")
                    except Exception as e:
                        result = f"Error executing {tool_call.name}: {str(e)}"
                        logger.error(f"  <- Error: {result}")

                    # Add tool result in Responses API format
                    input_items.append({
                        "type": "function_call_output",
                        "call_id": tool_call.call_id,
                        "output": result,
                    })

            # If we hit max iterations, get final response without tools
            logger.warning(f"Hit max iterations ({MAX_TOOL_ITERATIONS}), forcing final response")
            input_items.append({
                "role": "user",
                "content": "You have run out of tool calls. Summarize what you accomplished and what you could not complete.",
            })
            response = await self._call_llm(input_items, tools=None)
            return response.output_text or "I processed your request."

    async def check_health(self) -> tuple[bool, Optional[str]]:
        """Check if all services are healthy.

        Returns:
            Tuple of (is_healthy, error_message).
        """
        async with ObsidianRESTClient(
            self._settings.obsidian_api_url,
            self._settings.obsidian_api_key,
        ) as rest_client:
            if not await rest_client.health_check():
                return False, "Obsidian REST API is not available"

        return True, None
