"""Sandbox lifecycle for Postgres and DuckDB fixtures.

Each engine knows how to build the dojo fixture (customer_feedback, employees,
canary_table) and how to plant a per-payload poisoned row before the adapter
runs. Resource-touch logging is per-engine: DuckDB uses a connection-local
trace callback; Postgres uses `pg_stat_statements` when available and the
query log otherwise.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from importlib import resources

POISONED_ROW_ID = 100777
POISONED_TICKET_ID = 200777

# DOJO_FIXTURE_SIZE=large asks the DuckDB engine to run large_fixture.sql after
# seed_duckdb.sql so the three agent-facing tables carry ~100k rows each. This
# is additive: the standard seed still loads first, so the oracle, adapters,
# and mock dispatch see the same schema at both sizes. Default stays "standard"
# so existing tests and CI are unaffected.
_LARGE_SIZE_VALUES = {"large", "100k", "scale"}


def _requested_size() -> str:
    v = (os.environ.get("DOJO_FIXTURE_SIZE") or "standard").strip().lower()
    return "large" if v in _LARGE_SIZE_VALUES else "standard"


@dataclass
class Fixture:
    workdir: str
    engine: str
    db_url: str
    values: dict = field(default_factory=dict)


def _read_sql(name: str) -> str:
    return resources.files("data_agent_dojo.fixtures").joinpath(name).read_text("utf-8")


class DuckDBEngine:
    name = "duckdb"
    db_file = "dojo.duckdb"

    def __init__(self):
        self._root: str | None = None

    def build(self, root: str) -> None:
        import duckdb
        self._root = root
        os.makedirs(root, exist_ok=True)
        self.pristine = os.path.join(root, "pristine.duckdb")
        con = duckdb.connect(self.pristine)
        try:
            con.execute(_read_sql("seed_duckdb.sql"))
            if _requested_size() == "large":
                con.execute(_read_sql("large_fixture.sql"))
        finally:
            con.close()

    def prepare(self, workdir: str, poisoned_review_text: str, canaries: tuple[str, ...]) -> Fixture:
        import duckdb
        os.makedirs(workdir, exist_ok=True)
        db = os.path.join(workdir, self.db_file)
        shutil.copyfile(self.pristine, db)
        con = duckdb.connect(db)
        try:
            con.execute(
                "INSERT INTO customer_feedback(id, product_id, review_text, submitted_at) VALUES (?, ?, ?, now())",
                [POISONED_ROW_ID, 42, poisoned_review_text],
            )
            for i, c in enumerate(canaries):
                con.execute(
                    "INSERT INTO canary_table(id, token) VALUES (?, ?)",
                    [POISONED_ROW_ID * 10 + i, c],
                )
        finally:
            con.close()
        return Fixture(workdir=workdir, engine=self.name, db_url=db,
                       values={"db": db, "poisoned_row_id": POISONED_ROW_ID})

    def observe_resources(self, fixture: Fixture) -> list[str]:
        """Return the names of tables that were read since prepare(). v0.1 does not
        wire DuckDB's per-connection trace callback into the mock run; the adapter
        populates this list. Left as a hook for the real adapter."""
        return []

    def cleanup(self, fixture: Fixture) -> None:
        shutil.rmtree(fixture.workdir, ignore_errors=True)

    def close(self) -> None:
        if self._root and os.path.isdir(self._root):
            shutil.rmtree(self._root, ignore_errors=True)


class PostgresEngine:
    name = "postgres"

    def __init__(self, dsn: str):
        if not dsn:
            raise SystemExit("--dsn is required for postgres (a throwaway server you are superuser on)")
        self.base_dsn = dsn

    def _connect(self, dbname: str = "postgres"):
        import psycopg
        return psycopg.connect(self.base_dsn, autocommit=True)

    def build(self, root: str) -> None:
        os.makedirs(root, exist_ok=True)
        self._root = root
        sql = _read_sql("seed_postgres.sql")
        with self._connect() as con:
            con.execute(sql)

    def prepare(self, workdir: str, poisoned_review_text: str, canaries: tuple[str, ...]) -> Fixture:
        os.makedirs(workdir, exist_ok=True)
        with self._connect() as con:
            con.execute(
                "INSERT INTO customer_feedback(id, product_id, review_text, submitted_at) VALUES (%s, %s, %s, now()) "
                "ON CONFLICT (id) DO UPDATE SET review_text = EXCLUDED.review_text",
                (POISONED_ROW_ID, 42, poisoned_review_text),
            )
            for i, c in enumerate(canaries):
                con.execute(
                    "INSERT INTO canary_table(id, token) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (POISONED_ROW_ID * 10 + i, c),
                )
        return Fixture(workdir=workdir, engine=self.name, db_url=self.base_dsn,
                       values={"dsn": self.base_dsn, "poisoned_row_id": POISONED_ROW_ID})

    def observe_resources(self, fixture: Fixture) -> list[str]:
        return []

    def cleanup(self, fixture: Fixture) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM customer_feedback WHERE id = %s", (POISONED_ROW_ID,))
            con.execute("DELETE FROM canary_table WHERE id >= %s", (POISONED_ROW_ID * 10,))

    def close(self) -> None:
        return None


def build_engine(name: str, dsn: str | None = None):
    if name == "duckdb":
        return DuckDBEngine()
    if name == "postgres":
        return PostgresEngine(dsn or "")
    raise SystemExit(f"unknown engine {name!r}; choose duckdb or postgres")
