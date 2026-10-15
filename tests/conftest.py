import os
import tempfile

import pytest


@pytest.fixture
def duckdb_path(tmp_path):
    pytest.importorskip("duckdb")
    yield str(tmp_path / "fixture.duckdb")


@pytest.fixture
def ephemeral_root():
    with tempfile.TemporaryDirectory(prefix="dojo-test-") as d:
        yield d
