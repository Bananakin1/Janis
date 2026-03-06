"""Quality gate fixtures and harness for live Janis validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.agent.orchestrator import Orchestrator
from src.backend.rest_client import ObsidianRESTClient
from src.config.settings import Settings


def pytest_addoption(parser):
    parser.addoption(
        "--run-qg",
        action="store_true",
        default=False,
        help="Run live quality gate tests that require Azure OpenAI and Obsidian.",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "qg: live quality gate tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-qg"):
        return
    skip_qg = pytest.mark.skip(reason="Quality gates require --run-qg.")
    for item in items:
        if "qg" in item.keywords:
            item.add_marker(skip_qg)


@dataclass
class CapturedToolCall:
    name: str
    args: dict
    result: str

    @property
    def target_path(self) -> str:
        for key in ("path", "file", "source", "destination", "note_name"):
            value = self.args.get(key)
            if isinstance(value, str):
                return value
        return ""

    @property
    def content(self) -> str:
        value = self.args.get("content")
        return value if isinstance(value, str) else ""


@dataclass
class QGResult:
    tool_calls: list[CapturedToolCall]
    response: str

    def has_tool_call(self, name: str, **kwargs) -> bool:
        for tool_call in self.tool_calls:
            if tool_call.name != name:
                continue
            matched = True
            for key, expected in kwargs.items():
                if key.endswith("_contains"):
                    if str(expected).lower() not in str(tool_call.args).lower():
                        matched = False
                        break
                elif str(tool_call.args.get(key, "")).lower() != str(expected).lower():
                    matched = False
                    break
            if matched:
                return True
        return False

    def find_tool_call(self, name: str) -> CapturedToolCall | None:
        for tool_call in self.tool_calls:
            if tool_call.name == name:
                return tool_call
        return None

    def find_write_call(self, target_contains: str) -> CapturedToolCall | None:
        write_tools = {"create_note", "update_note", "append_note", "upsert_note", "patch_note"}
        for tool_call in self.tool_calls:
            if tool_call.name in write_tools and target_contains.lower() in str(tool_call.args).lower():
                return tool_call
        return None


class QualityGateHarness:
    """Wraps the orchestrator and captures tool calls during execution."""

    def __init__(self, orchestrator: Orchestrator):
        self._orchestrator = orchestrator
        self.tool_calls: list[CapturedToolCall] = []
        self.response: str = ""
        self._original_execute = orchestrator._execute_tool
        orchestrator._execute_tool = self._capturing_execute

    async def _capturing_execute(self, tool_name, arguments, ctx):
        result = await self._original_execute(tool_name, arguments, ctx)
        result_text = result.content if hasattr(result, "content") else str(result)
        self.tool_calls.append(
            CapturedToolCall(name=tool_name, args=arguments, result=result_text)
        )
        return result

    async def run(self, message: str, author: str = "TestUser", user_id: str = "qg-user") -> QGResult:
        self.tool_calls.clear()
        self.response = await self._orchestrator.process_message(message, author=author, user_id=user_id)
        return QGResult(tool_calls=list(self.tool_calls), response=self.response)


@pytest.fixture(scope="session")
def qg_settings():
    try:
        return Settings()
    except ValidationError as exc:
        pytest.skip(f"Quality gate settings are not configured: {exc}")


@pytest.fixture
async def rest_client(qg_settings):
    async with ObsidianRESTClient(qg_settings.obsidian_api_url, qg_settings.obsidian_api_key) as client:
        if not await client.health_check():
            pytest.skip("Obsidian REST API is not available.")
        yield client


@pytest.fixture
def orchestrator(qg_settings):
    return Orchestrator(qg_settings)


@pytest.fixture
def qg_harness(orchestrator):
    return QualityGateHarness(orchestrator)


@pytest.fixture
async def snapshot_note(rest_client):
    snapshots: dict[str, str] = {}

    async def _snapshot(path: str):
        content = await rest_client.read_note(path)
        if content is not None:
            snapshots[path] = content

    yield _snapshot

    for path, content in snapshots.items():
        await rest_client.upsert_note(path, content)


@pytest.fixture(autouse=True)
async def qg_sandbox_cleanup(rest_client):
    yield
    try:
        sandbox_items = await rest_client.list_vault("_qg_sandbox")
    except Exception:
        return
    for item in sandbox_items:
        if str(item).endswith("/"):
            continue
        item_name = str(item).rstrip("/")
        if item_name.endswith(".md"):
            try:
                await rest_client.delete_note(f"_qg_sandbox/{item_name}")
            except Exception:
                pass
