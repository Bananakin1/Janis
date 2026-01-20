# TODO

Reference: [SPEC.md](./SPEC.md)

## Loop Protocol

```
1. Read SPEC.md for current module
2. Use the skill research-first to gather best practices and find official documentation
3. Implement module
4. Write unit tests
5. Run: pytest tests/unit/ -v
6. If tests fail → fix and rerun
7. If tests pass → check box, commit, next module
8. When all boxes checked → output completion promise
```

## Modules

- [x] Project setup: `pyproject.toml`, `.env.example`, package structure
- [x] Config: `src/config/settings.py` with pydantic-settings
- [x] Vault index: `src/obsidian/vault_index.py` wrapping obsidiantools
- [x] REST client: `src/obsidian/rest_client.py` with httpx async
- [x] Tools: `src/agent/tools.py` Pydantic models + OpenAI schemas
- [x] Prompts: `src/agent/prompts.py` system prompt template
- [x] Orchestrator: `src/agent/orchestrator.py` tool-calling loop
- [x] Discord bot: `src/bot/client.py` message handler
- [x] Entry point: `src/main.py` async main with graceful shutdown

## Completion

All boxes checked.

<promise>COMPLETE</promise>
