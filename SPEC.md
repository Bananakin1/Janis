# Discord-Obsidian Agent Specification

## Overview

A Python agent that captures natural language messages from a Discord channel, interprets user intent using Azure OpenAI, and executes operations on a local Obsidian vault via the Local REST API plugin.

## Goals & Success Criteria

- Process natural language note requests from Discord
- Maintain graph integrity through consistent wikilink usage
- Provide clear feedback on all operations
- Handle edge cases gracefully (ambiguity, offline states, duplicates)

**Success metrics:**
- All created notes have valid frontmatter
- Wikilinks resolve to existing notes or auto-created stubs
- User receives detailed confirmation for every operation

## Tech Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Runtime | Python | >=3.11 |
| Discord Integration | discord.py | >=2.3 |
| LLM | Azure OpenAI | API 2024-08-01-preview |
| Vault Index | obsidiantools | >=0.10 |
| HTTP Client | httpx | >=0.27 |
| Configuration | pydantic-settings | >=2.1 |
| Data Validation | pydantic | >=2.5 |
| Environment | python-dotenv | >=1.0 |

## Architecture

```
Discord Channel
      |
      v
+------------------+
|   Discord Bot    |  (discord.py)
|   on_message     |
+------------------+
      |
      v
+------------------+
|  Orchestrator    |  (Tool-calling loop)
|  Azure OpenAI    |
+------------------+
      |
      v
+------------------+     +------------------+
|  VaultIndex      |<--->|  ObsidianREST    |
|  (obsidiantools) |     |  (httpx)         |
+------------------+     +------------------+
      |                        |
      v                        v
+----------------------------------------+
|           Obsidian Vault               |
|         (Local filesystem)             |
+----------------------------------------+
```

## Tools

Three tools exposed to the LLM agent:

### 1. search_notes
- **Purpose**: Find notes by name
- **Input**: `query: str`
- **Output**: List of matching note names
- **Use case**: Locate existing notes before creating wikilinks

### 2. read_note
- **Purpose**: Read content of an existing note
- **Input**: `note_name: str`
- **Output**: Markdown content or null
- **Use case**: Check existing content before updating

### 3. upsert_note
- **Purpose**: Create or update a note
- **Input**: `note_name: str`, `content: str`, `folder: str (optional)`
- **Output**: Success/failure status
- **Use case**: Save new notes or modify existing ones

## Behavioral Rules

### Wikilink Handling
- When creating wikilinks to non-existent notes, **auto-create stub notes**
- Stub format: `# [Entity Name]\n\n[Type inferred by LLM].`
- Example: `# Sarah Chen\n\nPerson.`

### Ambiguity Resolution
- When entity references are ambiguous (e.g., "Sarah" matches multiple notes), **ask for clarification**
- Bot responds: "I found multiple matches: Sarah Chen, Sarah Miller. Which one did you mean?"
- Wait for user reply before proceeding

### Content Merging
- When upserting an existing note, **append new content** to the end
- Preserve all original content
- Add timestamp separator: `\n\n---\n\n## [Date]\n\n[New content]`

### Note Classification
- **LLM inference** determines note type from message content
- Types: Meeting, Person, Project, Topic, General
- Type determines target folder

### Folder Structure
- **Type-based organization:**
  - `Meetings/` - Meeting notes
  - `People/` - Person notes
  - `Projects/` - Project notes
  - `Topics/` - Topic/concept notes
  - `Inbox/` - Unclassified or general notes

### Frontmatter Generation
- All notes include **standard YAML frontmatter:**
```yaml
---
title: [Note Title]
type: [meeting|person|project|topic|general]
tags: [inferred-tags]
created: [ISO date]
related: [list of wikilinks]
---
```

### Vault Index
- **Refresh on each message** before processing
- Ensures accurate search results and backlink data

### Discord Feedback
- **Detailed response** after every operation
- Format: "Created [Note Name].md in [Folder]/ with links to [[Entity1]], [[Entity2]]"
- Include note type and any stub notes created

## Modules

### 1. config/settings.py
Pydantic settings model loading from `.env`:
- Discord token and channel ID
- Azure OpenAI credentials and deployment name
- Obsidian vault path and REST API credentials

### 2. obsidian/vault_index.py
Wrapper around obsidiantools library:
- `refresh()`: Rebuild in-memory index
- `get_backlinks(note_name)`: Get notes linking to a note
- `note_exists(note_name)`: Check if note exists
- `search_notes(query)`: Fuzzy search by name
- `get_vault_summary()`: Stats for system prompt

### 3. obsidian/rest_client.py
Async HTTP client for Obsidian Local REST API:
- `read_note(path)`: GET /vault/{path}
- `upsert_note(path, content)`: PUT /vault/{path}
- `search(query)`: POST /search/simple/

### 4. agent/tools.py
Pydantic models for tool parameters:
- `SearchNotesParams`
- `ReadNoteParams`
- `UpsertNoteParams`
- OpenAI function definitions list

### 5. agent/prompts.py
System prompt template with:
- Vault context injection (folders, recent notes, stats)
- Wikilink formatting rules
- Note structure guidelines
- Frontmatter requirements
- Ambiguity handling instructions

### 6. agent/orchestrator.py
Main agent logic:
- Initialize LLM client and vault services
- Refresh vault index before each request
- Process Discord messages through tool-calling loop
- Execute tools and return results to LLM
- Create stub notes for unresolved wikilinks
- Maximum 5 tool calls per request

### 7. bot/client.py
Discord bot implementation:
- Message handler for configured channel
- Typing indicator during processing
- Detailed response formatting
- Response chunking for long messages

### 8. main.py
Entry point:
- Initialize bot
- Start event loop
- Graceful shutdown handling

## Error Handling & Edge Cases

### Obsidian Offline
- If REST API unavailable, **fail immediately with message**
- Response: "Obsidian is not running. Please open it and try again."
- No retry or queue mechanism

### LLM Errors
- If Azure OpenAI fails, return error message to Discord
- Include error type (rate limit, timeout, auth) for debugging

### Invalid Note Paths
- Sanitize note names (remove special characters)
- Replace `/` `\` `:` `*` `?` `"` `<` `>` `|` with `-`

### Empty Messages
- Ignore empty or whitespace-only messages
- No response sent

### Long Responses
- Discord limit: 2000 characters
- Split into multiple messages if exceeded

## Constraints & Tradeoffs

| Constraint | Rationale |
|------------|-----------|
| Single Discord channel | Simplicity - avoid multi-channel routing |
| Local vault only | No sync complexity, REST API requires local Obsidian |
| 5 tool iterations max | Prevent infinite loops, bound latency |
| Index refresh per message | Accuracy over performance |
| No delete operation | Safety - destructive ops out of MVP scope |
| Self-signed HTTPS cert | Obsidian Local REST API limitation |

## File Structure

```
discord-obsidian-agent/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── obsidian/
│   │   ├── __init__.py
│   │   ├── vault_index.py
│   │   └── rest_client.py
│   ├── agent/
│   │   ├── __init__.py
│   │   ├── tools.py
│   │   ├── prompts.py
│   │   └── orchestrator.py
│   └── bot/
│       ├── __init__.py
│       └── client.py
├── tests/
│   └── unit/
│       ├── test_vault_index.py
│       ├── test_rest_client.py
│       ├── test_tools.py
│       └── test_orchestrator.py
├── .env.example
├── pyproject.toml
├── requirements.txt
├── SPEC.md
├── TODO.md
└── SETUP.md
```
