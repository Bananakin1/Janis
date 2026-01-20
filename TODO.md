# TODO

Reference: [SPEC.md](./SPEC.md)

## Loop Protocol

```
1. Read SPEC.md for current module
2. Implement module
3. Write unit tests
4. Run: pytest tests/unit/ -v
5. If tests fail → fix and rerun
6. If tests pass → check box, commit, next module
7. When all boxes checked → output completion promise
```

## Modules

- [ ] Project setup: `pyproject.toml`, `.env.example`, package structure
- [ ] Config: `src/config/settings.py` with pydantic-settings
- [ ] Vault index: `src/obsidian/vault_index.py` wrapping obsidiantools
- [ ] REST client: `src/obsidian/rest_client.py` with httpx async
- [ ] Tools: `src/agent/tools.py` Pydantic models + OpenAI schemas
- [ ] Prompts: `src/agent/prompts.py` system prompt template
- [ ] Orchestrator: `src/agent/orchestrator.py` tool-calling loop
- [ ] Discord bot: `src/bot/client.py` message handler
- [ ] Entry point: `src/main.py` async main with graceful shutdown

## Completion

All boxes checked.

<promise>COMPLETE</promise>
