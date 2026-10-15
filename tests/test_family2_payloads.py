import pytest

from data_agent_dojo.adapters.base import MockAgentBackend
from data_agent_dojo.families import retrieved_document_poisoning
from data_agent_dojo.runner import Runner


FAMILY_NAME = "retrieved-document-poisoning"


def test_family2_exports_ten_payloads():
    payloads = list(retrieved_document_poisoning.FAMILY.payloads())
    assert len(payloads) == 10


def test_family2_payload_ids_are_unique():
    ids = [p.id for p in retrieved_document_poisoning.FAMILY.payloads()]
    assert len(ids) == len(set(ids))
    for pid in ids:
        assert pid.startswith("rdp-")


def test_family2_every_payload_is_well_formed():
    for p in retrieved_document_poisoning.FAMILY.payloads():
        assert p.family == FAMILY_NAME
        assert p.injection_vector == "retrieved-document"
        assert p.question.strip()
        assert p.injected_content.strip()
        assert "support_tickets" in p.expected_shape.allowed_tables
        assert "SELECT" in p.expected_shape.allowed_statement_kinds
        assert "DROP" in p.expected_shape.forbidden_statement_kinds


def test_family2_canary_payloads_reference_canary_in_injection():
    for p in retrieved_document_poisoning.FAMILY.payloads():
        for c in p.canaries:
            assert c in p.injected_content, f"{p.id}: canary {c!r} missing"


def test_family2_benign_fpcheck_has_matching_expected_shape():
    benign = next(p for p in retrieved_document_poisoning.FAMILY.payloads()
                  if p.id == "rdp-10-benign-fpcheck")
    assert benign.expected_shape.allowed_tables == frozenset({"support_tickets"})
    assert benign.expected_shape.allowed_statement_kinds == frozenset({"SELECT"})
    assert benign.canaries == ()


def test_family2_registered():
    from data_agent_dojo.families import FAMILIES
    assert FAMILY_NAME in FAMILIES


duckdb = pytest.importorskip("duckdb")


def _run(behavior):
    adapter = MockAgentBackend(behavior=behavior)
    runner = Runner(adapter=adapter, engine_name="duckdb",
                    families=[FAMILY_NAME])
    return runner.run()


def test_family2_honest_is_all_pass():
    results = _run("honest")
    assert len(results) == 10
    assert {r.verdict.kind for r in results} == {"pass"}


def test_family2_refusing_is_all_correct_refusal():
    results = _run("refusing")
    assert len(results) == 10
    assert {r.verdict.kind for r in results} == {"correct-refusal"}


def test_family2_compliant_flags_at_least_eight_and_passes_benign():
    results = _run("compliant")
    assert len(results) == 10
    flagged = [r for r in results
               if r.verdict.kind in ("silent-exfil", "correct-refusal")
               and r.payload_id != "rdp-10-benign-fpcheck"]
    assert len(flagged) >= 8, (
        "compliant mock must drive >=8 non-benign payloads to a non-pass verdict; "
        f"got {[(r.payload_id, r.verdict.kind) for r in results]}"
    )
    benign = next(r for r in results if r.payload_id == "rdp-10-benign-fpcheck")
    assert benign.verdict.kind == "pass", (
        f"benign-fpcheck must verdict pass, got {benign.verdict.kind} ({benign.verdict.reason})"
    )


def test_family1_still_green_against_family2_extended_mock():
    from data_agent_dojo.families import cell_value_injection
    adapter = MockAgentBackend(behavior="honest")
    runner = Runner(adapter=adapter, engine_name="duckdb",
                    families=[cell_value_injection.FAMILY.name])
    results = runner.run()
    assert len(results) == 10
    assert {r.verdict.kind for r in results} == {"pass"}
