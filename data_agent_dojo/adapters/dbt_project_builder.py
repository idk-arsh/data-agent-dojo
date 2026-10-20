"""Build a throwaway dbt-duckdb project around a dojo fixture.

The dbt-mcp `show` tool runs `dbt show --inline <sql>` in a subprocess with the
project's working directory. For a real run we need a minimal dbt project whose
profile points at the per-payload DuckDB file the engine already prepared, plus
sources that name the fixture tables so a model author (or an agent) can select
from them. Nothing here talks to a network or to dbt Platform.
"""
from __future__ import annotations

import os
import textwrap

# The agent-facing tables the fixture seeds. Kept in sync with seed_duckdb.sql.
FIXTURE_TABLES = ("customer_feedback", "employees", "canary_table",
                  "support_tickets", "orders")


def build_project(project_dir: str, duckdb_path: str) -> str:
    """Write a minimal dbt-duckdb project into project_dir pointing at duckdb_path.

    Returns project_dir. Safe to call once per payload; it only writes files.
    """
    os.makedirs(project_dir, exist_ok=True)
    models_dir = os.path.join(project_dir, "models")
    os.makedirs(models_dir, exist_ok=True)
    # Keep an empty models dir so dbt parses cleanly; `show --inline` references
    # the fixture tables directly as main.<table>, so no sources.yml is needed
    # (a sources.yml that names tables dbt can't resolve breaks `dbt parse`).
    gk = os.path.join(models_dir, ".gitkeep")
    if not os.path.exists(gk):
        open(gk, "w").close()

    abs_db = os.path.abspath(duckdb_path).replace("\\", "/")

    with open(os.path.join(project_dir, "dbt_project.yml"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            name: dojo_target
            version: "1.0.0"
            config-version: 2
            profile: dojo_target
            model-paths: ["models"]
            quoting:
              database: false
              schema: false
              identifier: false
            """))

    # profiles.yml lives inside the project dir; DBT_PROFILES_DIR points here.
    with open(os.path.join(project_dir, "profiles.yml"), "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(f"""\
            dojo_target:
              target: dev
              outputs:
                dev:
                  type: duckdb
                  path: "{abs_db}"
                  threads: 1
            """))

    return project_dir
