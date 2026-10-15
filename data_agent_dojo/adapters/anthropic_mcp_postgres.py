"""Adapter: Anthropic reference postgres MCP server driven by a Claude agent.

The reference server (originally at `github.com/modelcontextprotocol/servers`,
now archived under `/src/postgres` of that repo) exposes a `query` tool over
stdio that runs read-only SELECTs against a Postgres DSN. This adapter spins
the server, hands a Claude or OpenAI client the question, intercepts the
tool-result that comes back, and (if `tool_result_override` is set) swaps in
the poisoned payload content before the agent sees it.

v0.1 ships with the live-LLM path stubbed: if no API key is in the env the
adapter yields a MockAgentBackend run so the CI suite is deterministic. The
real client path is a thin wrapper around `anthropic.Anthropic` with tool-use
loop; it will land in v0.2 along with the OpenAI equivalent.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .base import AdapterBase, AgentRun, MockAgentBackend

SERVER_REPO = "github.com/modelcontextprotocol/servers"
SERVER_PATH = "src/postgres"
SERVER_COMMAND_HINT = ["npx", "-y", "@modelcontextprotocol/server-postgres", "{dsn}"]


@dataclass
class AnthropicMcpPostgresAdapter:
    name: str = "anthropic-mcp-postgres"
    dsn: str | None = None
    model: str = "claude-opus-4-7"
    server_command: list[str] = field(default_factory=lambda: list(SERVER_COMMAND_HINT))
    _mock: MockAgentBackend | None = None

    def setup(self, fixture_path: str) -> None:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            self._mock = MockAgentBackend(behavior="honest")
            self._mock.setup(fixture_path)

    def teardown(self) -> None:
        if self._mock is not None:
            self._mock.teardown()

    def run(self, question: str, tool_result_override: dict[str, Any] | None = None) -> AgentRun:
        if self._mock is not None:
            return self._mock.run(question, tool_result_override)
        raise NotImplementedError(
            "live Anthropic + MCP postgres path lands in v0.2; set ANTHROPIC_API_KEY to run it then"
        )
