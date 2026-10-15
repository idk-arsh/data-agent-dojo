"""Adapter targeting the Vanna text-to-SQL framework (vannadb/vanna)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from .base import AdapterBase, AgentRun, MockAgentBackend

VANNA_PACKAGE_HINT = "vanna"
VANNA_API_KEY_ENVS = ("VANNA_API_KEY", "OPENAI_API_KEY")
LIVE_GATE_ENV = "DOJO_LIVE_VANNA"
CVE_REF = "CVE-2024-7764"


def _vanna_importable() -> bool:
    """Return True iff the vanna package can be imported in the current env."""
    try:
        import importlib
        importlib.import_module(VANNA_PACKAGE_HINT)
        return True
    except Exception:
        return False


def _has_key() -> bool:
    """Return True iff at least one Vanna-usable API key is in the environment."""
    return any(os.environ.get(k) for k in VANNA_API_KEY_ENVS)


def extract_tables(sql: str) -> list[str]:
    """Return the unqualified table names named in `sql`, lower-cased, de-duped."""
    try:
        import sqlglot
        from sqlglot import exp
    except Exception:
        return []
    try:
        stmts = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except Exception:
        try:
            stmts = [s for s in sqlglot.parse(sql) if s is not None]
        except Exception:
            return []
    seen: list[str] = []
    for stmt in stmts:
        cte_names = {c.alias_or_name.lower() for c in stmt.find_all(exp.CTE)}
        for t in stmt.find_all(exp.Table):
            if not (isinstance(t.this, exp.Identifier) and t.name):
                continue
            if not t.db and not t.catalog and t.name.lower() in cte_names:
                continue
            name = t.name.lower()
            if name not in seen:
                seen.append(name)
    return seen


@dataclass
class VannaTextToSqlAdapter:
    """Vanna text-to-SQL adapter; falls back to MockAgentBackend without config."""
    name: str = "vanna-text-to-sql"
    training_schema_path: str | None = None
    api_key: str | None = None
    model: str = "gpt-4o-mini"
    allowed_table: str = "customer_feedback"
    example_queries: list[str] = field(default_factory=lambda: [
        "SELECT id, product_id, review_text, submitted_at FROM customer_feedback ORDER BY submitted_at DESC LIMIT 10",
        "SELECT ticket_id, subject, body FROM support_tickets WHERE status = 'open'",
        "SELECT order_id, customer_id, total FROM orders WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'",
    ])
    _mock: MockAgentBackend | None = None
    _client: Any = None
    _fixture_path: str | None = None

    def setup(self, fixture_path: str) -> None:
        """Train or stub Vanna; fall back to MockAgentBackend when unconfigured."""
        self._fixture_path = fixture_path
        key = self.api_key or next((os.environ.get(k) for k in VANNA_API_KEY_ENVS if os.environ.get(k)), None)
        if not key or not _vanna_importable():
            self._mock = MockAgentBackend(behavior="honest", allowed_table=self.allowed_table)
            self._mock.setup(fixture_path)
            return
        # live path: not wired by default; must be explicitly gated so unit tests
        # and CI never make a network call.
        if os.environ.get(LIVE_GATE_ENV) != "1":
            self._mock = MockAgentBackend(behavior="honest", allowed_table=self.allowed_table)
            self._mock.setup(fixture_path)
            return
        # If someone opted into DOJO_LIVE_VANNA=1 we still refuse to run until v0.2.
        raise NotImplementedError(
            "live Vanna text-to-SQL path lands in v0.2; unset DOJO_LIVE_VANNA to run the mock"
        )

    def run(self, question: str, tool_result_override: dict[str, Any] | None = None) -> AgentRun:
        """Delegate to the mock backend; live path is stubbed for v0.2."""
        if self._mock is not None:
            run = self._mock.run(question, tool_result_override)
            extra: list[str] = []
            for stmt in run.sql_statements:
                for t in extract_tables(stmt):
                    if t not in run.touched_resources and t not in extra:
                        extra.append(t)
            if extra:
                run.touched_resources = list(run.touched_resources) + extra
            return run
        raise NotImplementedError(
            "live Vanna text-to-SQL path lands in v0.2; set an API key and DOJO_LIVE_VANNA=1 then"
        )

    def teardown(self) -> None:
        """Release any Vanna client or mock state the setup opened."""
        if self._mock is not None:
            self._mock.teardown()
            self._mock = None
        if self._client is not None:
            close = getattr(self._client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            self._client = None
