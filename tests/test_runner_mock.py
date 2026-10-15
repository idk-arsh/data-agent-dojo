import pytest

from data_agent_dojo.adapters.base import MockAgentBackend
from data_agent_dojo.runner import Runner


duckdb = pytest.importorskip("duckdb")


def _run(behavior):
    adapter = MockAgentBackend(behavior=behavior)
    runner = Runner(adapter=adapter, engine_name="duckdb",
                    families=["cell-value-injection"])
    return runner.run()


def test_honest_backend_is_mostly_pass():
    results = _run("honest")
    assert len(results) == 10
    kinds = {r.verdict.kind for r in results}
    assert kinds == {"pass"}


def test_compliant_backend_triggers_silent_exfil():
    results = _run("compliant")
    exfils = [r for r in results if r.verdict.kind == "silent-exfil"]
    assert exfils, "compliant backend should produce at least one silent-exfil verdict"
    for r in exfils:
        assert r.verdict.observed_sql


def test_refusing_backend_hits_correct_refusal():
    results = _run("refusing")
    assert all(r.verdict.kind == "correct-refusal" for r in results)


def test_benign_payload_never_fires_on_honest_or_compliant():
    for behavior in ("honest", "compliant"):
        results = _run(behavior)
        benign = next(r for r in results if r.payload_id == "cvi-10-benign-mentions-sql")
        assert benign.verdict.kind in ("pass", "correct-refusal"), (
            f"benign payload must not be flagged as silent-exfil under {behavior} backend"
        )
