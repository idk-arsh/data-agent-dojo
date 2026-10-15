from data_agent_dojo.families import cell_value_injection


def test_ten_payloads():
    payloads = list(cell_value_injection.FAMILY.payloads())
    assert len(payloads) == 10


def test_every_payload_is_well_formed():
    for p in cell_value_injection.FAMILY.payloads():
        assert p.id.startswith("cvi-")
        assert p.family == "cell-value-injection"
        assert p.question.strip(), f"{p.id} missing question"
        assert p.injected_content.strip(), f"{p.id} missing injected_content"
        assert "customer_feedback" in p.expected_shape.allowed_tables
        assert "SELECT" in p.expected_shape.allowed_statement_kinds
        assert "INSERT" in p.expected_shape.forbidden_statement_kinds
        assert "DROP" in p.expected_shape.forbidden_statement_kinds


def test_unique_ids():
    ids = [p.id for p in cell_value_injection.FAMILY.payloads()]
    assert len(ids) == len(set(ids))


def test_canary_payloads_reference_canary_in_injection():
    for p in cell_value_injection.FAMILY.payloads():
        for c in p.canaries:
            assert c in p.injected_content, f"{p.id}: canary {c!r} missing from injected_content"
