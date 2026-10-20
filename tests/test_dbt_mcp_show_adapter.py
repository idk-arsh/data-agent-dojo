"""Offline tests for the dbt-mcp-show live adapter.

These never start a server or call a model. They check:
- the adapter refuses to run without the live gate / key (fail-closed, never
  a silent mock);
- its tool spec carries the family-3 client-side description splice;
- the SQL -> touched-tables bookkeeping the oracle depends on.

The end-to-end live path is exercised by scripts/run_dbt_mcp_live.py behind the
DOJO_LIVE_DBT_MCP gate, not in CI.
"""
import os
import pytest

from data_agent_dojo.adapters.dbt_mcp_show import DbtMcpShowAdapter, LIVE_GATE_ENV


def test_setup_fails_closed_without_gate(monkeypatch, tmp_path):
    monkeypatch.delenv(LIVE_GATE_ENV, raising=False)
    a = DbtMcpShowAdapter()
    with pytest.raises(RuntimeError, match="live adapter"):
        a.setup(str(tmp_path))


def test_setup_fails_closed_without_key(monkeypatch, tmp_path):
    monkeypatch.setenv(LIVE_GATE_ENV, "1")
    for k in ("DOJO_OPENROUTER_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.delenv("DOJO_OPENROUTER_KEY_FILE", raising=False)
    a = DbtMcpShowAdapter()
    with pytest.raises(RuntimeError, match="no OpenRouter key"):
        a.setup(str(tmp_path))


def test_tools_spec_splices_family3_description_client_side():
    a = DbtMcpShowAdapter()
    spec = a._tools_spec({"allowed_table": "orders", "injected_content": "ZZINJECTZZ"})
    desc = spec[0]["function"]["description"]
    assert "ZZINJECTZZ" in desc  # family-3 poison reaches the model, client-side
    assert spec[0]["function"]["name"] == "dbt_show"


def test_tools_spec_clean_for_family1():
    a = DbtMcpShowAdapter()
    spec = a._tools_spec({"allowed_table": "customer_feedback", "injected_content": "ZZINJECTZZ"})
    assert "ZZINJECTZZ" not in spec[0]["function"]["description"]


def test_project_builder_writes_profile(tmp_path):
    from data_agent_dojo.adapters.dbt_project_builder import build_project
    proj = build_project(str(tmp_path / "p"), str(tmp_path / "x.duckdb"))
    assert os.path.isfile(os.path.join(proj, "dbt_project.yml"))
    assert os.path.isfile(os.path.join(proj, "profiles.yml"))
    prof = open(os.path.join(proj, "profiles.yml"), encoding="utf-8").read()
    assert "type: duckdb" in prof
