"""Scale smoke test. Opt-in with `pytest -m slow`.

Verifies the large (100k-row) DuckDB fixture loads and that mock-honest stays
at 30/30 pass across the three families at that size. Marked `slow` so default
`pytest` runs (CI's cheap path) skip it.
"""
from __future__ import annotations

import os

import pytest

from data_agent_dojo.adapters.base import MockAgentBackend
from data_agent_dojo.runner import Runner


@pytest.mark.slow
def test_mock_honest_100k_all_families_pass(monkeypatch):
    pytest.importorskip("duckdb")
    monkeypatch.setenv("DOJO_FIXTURE_SIZE", "large")
    adapter = MockAgentBackend(behavior="honest")
    runner = Runner(
        adapter=adapter,
        engine_name="duckdb",
        families=[
            "cell-value-injection",
            "retrieved-document-poisoning",
            "mcp-tool-description-poisoning",
        ],
    )
    results = runner.run()
    assert len(results) == 30, f"expected 30 payloads, got {len(results)}"
    kinds = [r.verdict.kind for r in results]
    non_pass = [r for r in results if r.verdict.kind != "pass"]
    assert all(k == "pass" for k in kinds), (
        f"mock-honest at 100k scale produced non-pass verdicts: "
        + ", ".join(f"{r.payload_id}:{r.verdict.kind}" for r in non_pass)
    )
