# Janis - Discord-Obsidian Agent

Discord bot that manages an Obsidian vault via natural language using Azure OpenAI Responses API.

## Quick Commands

```bash
# Run the bot
python -m src.main

# Run tests
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v

# Install (editable mode with dev deps)
pip install -e ".[dev]"
```

## Architecture

```
Discord Message → ObsidianBot → Orchestrator → Azure OpenAI (tool-calling loop)
                                     ↓
                              VaultIndex + RESTClient → Obsidian Vault
```

**Tool-calling loop**: Max 8 iterations. Uses Responses API - reasoning handled server-side, preventing chain-of-thought leakage.

**Working memory**: In-memory ring buffer (`deque`, maxlen=4) stores the last 2 conversation turns (user + assistant each). History is injected into `input_items` before the current message. User messages are attributed as `[DisplayName]: message`. `process_message(user_message, author="User")` accepts an `author` parameter passed from `message.author.display_name` in Discord.

## Project Structure

```
src/
├── main.py                 # Entry point, signal handling
├── config/settings.py      # Pydantic settings from .env
├── bot/client.py           # Discord message handler
├── agent/
│   ├── orchestrator.py     # Core agent logic, tool execution
│   ├── tools.py            # Pydantic models + OpenAI function schemas
│   └── prompts.py          # System prompt with vault context
└── obsidian/
    ├── vault_index.py      # obsidiantools wrapper for search/backlinks
    └── rest_client.py      # Async HTTP client for REST API
```

## Key Files

| File | Purpose |
|------|---------|
| `src/agent/orchestrator.py` | Tool-calling loop, execute search/read/upsert/ask_clarification |
| `src/agent/tools.py` | Four tools: search_notes, read_note, upsert_note, ask_clarification |
| `src/bot/client.py` | Discord integration, message chunking (2000 char limit) |
| `src/obsidian/rest_client.py` | Async HTTP to Obsidian REST API (self-signed cert) |

## Code Style

- Async-first: Use `async/await` for I/O operations
- Type hints required on all function signatures
- Pydantic for data validation and settings
- httpx for HTTP (not requests)
- pathlib.Path for filesystem operations

## Tech Stack

- **Python 3.11+**
- **discord.py** - Bot framework
- **openai** - Azure OpenAI SDK
- **httpx** - Async HTTP client
- **pydantic/pydantic-settings** - Validation and config
- **obsidiantools** - Vault indexing
- **tenacity** - Retry/backoff for API calls
- **pytest/pytest-asyncio** - Testing

## Environment Variables

Required in `.env`:
```
DISCORD_TOKEN
DISCORD_CHANNEL_ID
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_API_KEY
OBSIDIAN_VAULT_PATH        # Windows: C:\Users\...\ObsidianVault
OBSIDIAN_API_KEY
```

Optional:
```
AZURE_OPENAI_DEPLOYMENT    # default: gpt-4o (currently set to gpt-5.2)
OBSIDIAN_API_HOST          # default: 127.0.0.1
OBSIDIAN_API_PORT          # default: 27124
DEFAULT_NOTE_FOLDER        # default: Inbox
REASONING_EFFORT           # low/medium/high (default: medium)
```

## Azure OpenAI Responses API

This project uses the v1 Responses API (not Chat Completions):
- Endpoint: `{AZURE_OPENAI_ENDPOINT}/openai/v1/responses`
- No `api-version` parameter required
- Reasoning traces handled server-side (prevents GPT-5 chain-of-thought leakage)
- Tool format is flat (not nested under `function` key)

## Windows Compatibility

This project runs natively on Windows PowerShell (no WSL required).

**Platform-specific code:**
- `src/main.py:41` - SIGTERM handler skipped on Windows (only SIGINT/Ctrl+C)
- `src/agent/orchestrator.py` - Uses `Path.as_posix()` for REST API paths
- `src/agent/orchestrator.py` - `_to_relative_path()` normalizes paths from obsidiantools

**Path handling:** Always use `pathlib.Path`. For REST API URLs, convert with `.as_posix()` to ensure forward slashes.

## Testing

Tests use mocks for external services (Discord, Azure OpenAI, Obsidian REST API).

```bash
# Unit tests - isolated component testing
python -m pytest tests/unit/ -v

# Integration tests - component interactions
python -m pytest tests/integration/ -v
```

## Common Patterns

### Adding a new tool

1. Add Pydantic model in `src/agent/tools.py`
2. Add OpenAI function schema in `get_tool_definitions()`
3. Add execution logic in `orchestrator.py:_execute_tool()`

### REST API calls

```python
async with ObsidianRESTClient(url, key) as client:
    content = await client.read_note("Folder/Note")  # forward slashes
    await client.upsert_note("Folder/Note", "content")
```

### Path conversions

```python
# Windows path to REST API path
rel_path = note_path.relative_to(vault_path)
api_path = rel_path.as_posix()  # Always forward slashes
```

## API Resilience

**Retry/backoff** with tenacity for transient failures:
- LLM calls: 3 attempts, exponential backoff (0.5s-30s), retries on `APIError`, `APIConnectionError`, `RateLimitError`
- REST calls: 3 attempts, exponential backoff (0.25s-10s), retries on `ConnectError`, `TimeoutException`

**Strict mode** for tool definitions:
- All tools use `strict: true` for reliable schema adherence
- `additionalProperties: false` on all parameter objects
- `parallel_tool_calls: false` (required for strict mode)

## Meeting Note Convention

Notes in `Meetings/` follow a **company-keyed** structure for client/prospect meetings and **person-keyed** for individual contacts.

**Company notes** (e.g., `ITK.md`, `Curinos.md`):
- People table at the top with Name, Role, Notes columns
- Meetings in reverse chronological order
- Each meeting entry has `**With:** [attendees]` line
- One note per company -- all meetings with anyone from that company go here

**Individual notes** (e.g., `Reed Yamaguchi.md`, `Anthony Saetsugu.md`):
- Used for advisors, solo practitioners, legal contacts
- Standard date sections without People table

**Tagging:** Tags come from the vault's `Tag Registry` note. The system prompt instructs the LLM to `read_note('Tag Registry')` before creating notes, so tag values stay in sync without hardcoding.

The system prompt in `src/agent/prompts.py` encodes these conventions.

## Gotchas

- Obsidian REST API requires self-signed cert: `verify=False` in httpx
- Discord message limit: 2000 chars (auto-chunked in client.py)
- Vault index refreshes on every message (accuracy over performance)
- No delete tool by design (safety)
- LLM controls all output formatting (dates, separators) - orchestrator only strips frontmatter on appends
- Vault index may return absolute or relative paths - use `_to_relative_path()` to normalize
- Uses `AsyncOpenAI` (not `AsyncAzureOpenAI`) with custom `base_url` for Responses API
