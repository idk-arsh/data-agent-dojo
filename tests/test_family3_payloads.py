import pytest

from data_agent_dojo.adapters.base import MockAgentBackend
from data_agent_dojo.families import mcp_tool_description_poisoning
from data_agent_dojo.runner import Runner


FAMILY_NAME = "mcp-tool-description-poisoning"
BENIGN_ID = "td-10-benign-fpcheck"


def test_family3_exports_ten_payloads():
    payloads = list(mcp_tool_description_poisoning.FAMILY.payloads())
    assert len(payloads) == 10


def test_family3_every_payload_is_well_formed():
    for p in mcp_tool_description_poisoning.FAMILY.payloads():
        assert p.id.startswith("td-")
        assert p.family == FAMILY_NAME
        assert p.injection_vector == "mcp-tool-description"
        assert p.question.strip(), f"{p.id} missing question"
        assert p.injected_content.strip(), f"{p.id} missing injected_content"
        assert "orders" in p.expected_shape.allowed_tables
        assert "SELECT" in p.expected_shape.allowed_statement_kinds
        assert "INSERT" in p.expected_shape.forbidden_statement_kinds
        assert "DROP" in p.expected_shape.forbidden_statement_kinds


def test_family3_payload_ids_are_unique():
    ids = [p.id for p in mcp_tool_description_poisoning.FAMILY.payloads()]
    assert len(ids) == len(set(ids))


def test_family3_canary_payloads_reference_canary_in_injection():
    found_canary = False
    for p in mcp_tool_description_poisoning.FAMILY.payloads():
        for c in p.canaries:
            found_canary = True
            assert c in p.injected_content, (
                f"{p.id}: canary {c!r} missing from injected_content"
            )
    assert found_canary, "expected at least one Family-3 payload to carry a canary string"


def test_family3_benign_fpcheck_has_matching_expected_shape():
    payloads = {p.id: p for p in mcp_tool_description_poisoning.FAMILY.payloads()}
    assert BENIGN_ID in payloads, "benign false-positive-check payload missing"
    p = payloads[BENIGN_ID]
    assert p.expected_shape.allowed_tables == frozenset({"orders"})
    assert "SELECT" in p.expected_shape.allowed_statement_kinds
    # the benign payload must not carry a canary (it has nothing to exfil)
    assert p.canaries == ()


duckdb = pytest.importorskip("duckdb")


def _run(behavior):
    adapter = MockAgentBackend(behavior=behavior)
    runner = Runner(adapter=adapter, engine_name="duckdb",
                    families=[FAMILY_NAME])
    return runner.run()


def test_family3_honest_backend_is_all_pass():
    results = _run("honest")
    assert len(results) == 10
    assert {r.verdict.kind for r in results} == {"pass"}


def test_family3_refusing_backend_is_all_correct_refusal():
    results = _run("refusing")
    assert len(results) == 10
    assert all(r.verdict.kind == "correct-refusal" for r in results)


def test_family3_compliant_backend_triggers_silent_exfils():
    results = _run("compliant")
    assert len(results) == 10

    by_id = {r.payload_id: r for r in results}

    # Benign false-positive-check MUST verdict pass under compliant too.
    assert by_id[BENIGN_ID].verdict.kind == "pass", (
        f"benign fpcheck should stay pass, got {by_id[BENIGN_ID].verdict.kind}: "
        f"{by_id[BENIGN_ID].verdict.reason}"
    )

    # At least 8 of 10 payloads must land as silent-exfil or correct-refusal
    # (not pass) under the compliant mock.
    non_pass = [r for r in results
                if r.verdict.kind in ("silent-exfil", "correct-refusal")]
    assert len(non_pass) >= 8, (
        f"expected >=8 non-pass verdicts under compliant, got {len(non_pass)}: "
        + ", ".join(f"{r.payload_id}={r.verdict.kind}" for r in results)
    )
