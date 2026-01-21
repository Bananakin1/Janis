"""Agent orchestrator with tool-calling loop."""

import json
import re
from datetime import datetime
from typing import Optional

from openai import AsyncAzureOpenAI

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

MAX_TOOL_ITERATIONS = 5


class Orchestrator:
    """Main agent orchestrator for processing messages through Azure OpenAI."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the orchestrator.

        Args:
            settings: Application settings.
        """
        self._settings = settings
        self._vault_index = VaultIndex(settings.obsidian_vault_path)
        self._llm = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
        )

    def _sanitize_note_name(self, name: str) -> str:
        """Sanitize a note name by replacing invalid characters.

        Args:
            name: Original note name.

        Returns:
            Sanitized note name.
        """
        return INVALID_CHARS.sub("-", name).strip()

    def _strip_frontmatter(self, content: str) -> str:
        """Strip YAML frontmatter from content if present.

        Args:
            content: Note content that may contain frontmatter.

        Returns:
            Content with frontmatter removed.
        """
        # Match YAML frontmatter: starts with ---, ends with ---
        frontmatter_pattern = re.compile(r'^---\s*\n.*?\n---\s*\n?', re.DOTALL)
        return frontmatter_pattern.sub('', content).lstrip()

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
                rel_path = note_path.relative_to(self._settings.obsidian_vault_path)
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
            note_name = self._sanitize_note_name(params.note_name)
            folder = params.folder or self._settings.default_note_folder

            # Build the full path
            path = f"{folder}/{note_name}"

            # Check if note exists and merge content if so
            existing = await rest_client.read_note(path)
            if existing:
                today = datetime.now().strftime("%Y-%m-%d")
                # Strip any YAML frontmatter from content being appended
                content_to_append = self._strip_frontmatter(params.content)
                merged_content = f"{existing}\n\n---\n\n## {today}\n\n{content_to_append}"
                await rest_client.upsert_note(path, merged_content)
                return f"Updated note '{note_name}' in {folder}/"
            else:
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
        system_prompt = build_system_prompt(vault_summary)

        messages = [
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
            for _ in range(MAX_TOOL_ITERATIONS):
                response = await self._llm.chat.completions.create(
                    model=self._settings.azure_openai_deployment,
                    messages=messages,
                    tools=get_tool_definitions(),
                    tool_choice="auto",
                    max_completion_tokens=4096,
                    reasoning_effort=self._settings.reasoning_effort,
                )

                assistant_message = response.choices[0].message

                # If no tool calls, return the response
                if not assistant_message.tool_calls:
                    return assistant_message.content or "I processed your request."

                # Add assistant message with tool calls to history
                messages.append(assistant_message.model_dump())

                # Execute each tool call
                for tool_call in assistant_message.tool_calls:
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                        result = await self._execute_tool(
                            tool_call.function.name,
                            arguments,
                            rest_client,
                        )
                    except Exception as e:
                        result = f"Error executing {tool_call.function.name}: {str(e)}"

                    # Add tool result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    })

            # If we hit max iterations, get final response
            response = await self._llm.chat.completions.create(
                model=self._settings.azure_openai_deployment,
                messages=messages,
            )
            return response.choices[0].message.content or "I processed your request."

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
