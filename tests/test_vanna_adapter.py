"""Tests for the Vanna text-to-SQL adapter: no network, no vanna install."""
from __future__ import annotations

import pytest

from data_agent_dojo.adapters.base import MockAgentBackend
from data_agent_dojo.adapters.vanna_text_to_sql import (
    VANNA_API_KEY_ENVS,
    VannaTextToSqlAdapter,
    extract_tables,
)
from data_agent_dojo.cli import ADAPTERS
from data_agent_dojo.runner import Runner


duckdb = pytest.importorskip("duckdb")


def _clear_vanna_keys(monkeypatch):
    for k in VANNA_API_KEY_ENVS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("DOJO_LIVE_VANNA", raising=False)


def test_vanna_adapter_setup_falls_back_without_key(monkeypatch, tmp_path):
    _clear_vanna_keys(monkeypatch)
    adapter = VannaTextToSqlAdapter()
    adapter.setup(str(tmp_path))
    try:
        assert isinstance(adapter._mock, MockAgentBackend)
        assert adapter._mock.behavior == "honest"
    finally:
        adapter.teardown()


def test_vanna_adapter_run_without_key_yields_honest_pass(monkeypatch):
    _clear_vanna_keys(monkeypatch)
    adapter = VannaTextToSqlAdapter()
    runner = Runner(adapter=adapter, engine_name="duckdb",
                    families=["cell-value-injection"])
    results = runner.run()
    assert len(results) == 10
    assert {r.verdict.kind for r in results} == {"pass"}


def test_vanna_adapter_touched_resources_populated():
    sql = "SELECT id, product_id FROM customer_feedback ORDER BY submitted_at DESC LIMIT 10"
    tables = extract_tables(sql)
    assert "customer_feedback" in tables

    joined = (
        "SELECT cf.id, e.email FROM customer_feedback cf "
        "JOIN employees e ON e.id = cf.product_id"
    )
    assert set(extract_tables(joined)) == {"customer_feedback", "employees"}

    cte = (
        "WITH recent AS (SELECT id FROM customer_feedback) "
        "SELECT * FROM recent JOIN orders ON orders.id = recent.id"
    )
    tables_cte = extract_tables(cte)
    # CTE name 'recent' must be stripped; real tables remain.
    assert "recent" not in tables_cte
    assert "customer_feedback" in tables_cte
    assert "orders" in tables_cte

    assert extract_tables("NOT SQL AT ALL ;;;") == []


def test_vanna_adapter_name_is_registered():
    adapter = VannaTextToSqlAdapter()
    assert adapter.name == "vanna-text-to-sql"
    assert "vanna-text-to-sql" in ADAPTERS
    built = ADAPTERS["vanna-text-to-sql"]()
    assert isinstance(built, VannaTextToSqlAdapter)


def test_vanna_adapter_live_gate_requires_explicit_opt_in(monkeypatch, tmp_path):
    """DOJO_LIVE_VANNA=1 should attempt the live path; without it we mock."""
    _clear_vanna_keys(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    adapter = VannaTextToSqlAdapter()
    # With a key but no live gate AND no vanna install, we still land on the mock.
    adapter.setup(str(tmp_path))
    try:
        assert isinstance(adapter._mock, MockAgentBackend)
    finally:
        adapter.teardown()
