"""data-agent-dojo: red-team benchmark for data-access agents.

  data-agent-dojo run --adapter anthropic-mcp-postgres --families cell-value-injection
  data-agent-dojo list
  data-agent-dojo report <results.json>
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .adapters.anthropic_mcp_postgres import AnthropicMcpPostgresAdapter
from .adapters.base import MockAgentBackend
from .adapters.vanna_text_to_sql import VannaTextToSqlAdapter
from .families import FAMILIES
from .report import has_silent_exfil, to_json, to_markdown
from .runner import Runner, available_families

ADAPTERS = {
    "anthropic-mcp-postgres": AnthropicMcpPostgresAdapter,
    "vanna-text-to-sql": VannaTextToSqlAdapter,
    "mock-honest": lambda: MockAgentBackend(behavior="honest"),
    "mock-compliant": lambda: MockAgentBackend(behavior="compliant"),
    "mock-refusing": lambda: MockAgentBackend(behavior="refusing"),
}


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(prog="data-agent-dojo", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run selected families against an adapter")
    r.add_argument("--adapter", required=True, choices=sorted(ADAPTERS))
    r.add_argument("--engine", default="duckdb", choices=["duckdb", "postgres"])
    r.add_argument("--fixture", default="standard", choices=["standard", "large"],
                   help="duckdb fixture size: 'standard' (default) or 'large' (~100k rows per agent-facing table)")
    r.add_argument("--dsn", help="postgres only: superuser URL of a THROWAWAY server")
    r.add_argument("--families", default="cell-value-injection",
                   help="comma-separated family names (default: cell-value-injection)")
    r.add_argument("--only", help="comma-separated substrings of payload ids to run")
    r.add_argument("--json", help="write the JSON report here")
    r.add_argument("--markdown", help="write the Markdown report here")

    sub.add_parser("list", help="list available families and payloads")

    rp = sub.add_parser("report", help="render a Markdown report from a saved JSON run")
    rp.add_argument("path")

    a = ap.parse_args(argv)

    if a.cmd == "list":
        for name, fam in FAMILIES.items():
            print(f"{name}: {fam.description}")
            for p in fam.payloads():
                print(f"  - {p.id} ({p.severity}): {p.title}")
        return 0

    if a.cmd == "report":
        with open(a.path, encoding="utf-8") as f:
            data = json.load(f)
        meta = {k: data.get(k) for k in ("adapter", "engine", "families")}
        # reconstruct minimal RunResult-like objects for rendering only
        print(_render_from_json(data, meta))
        return 0

    if a.fixture == "large":
        os.environ["DOJO_FIXTURE_SIZE"] = "large"
    adapter_factory = ADAPTERS[a.adapter]
    adapter = adapter_factory()
    families = [f.strip() for f in a.families.split(",") if f.strip()]
    bad = [f for f in families if f not in available_families()]
    if bad:
        ap.error(f"unknown families: {', '.join(bad)}; known: {', '.join(available_families())}")

    runner = Runner(adapter=adapter, engine_name=a.engine, dsn=a.dsn,
                    families=families,
                    only=a.only.split(",") if a.only else None)
    print(f"data-agent-dojo {__version__}: adapter={a.adapter} engine={a.engine} families={families}")
    results = runner.run()
    meta = {"version": __version__, "adapter": a.adapter, "engine": a.engine, "families": families}
    md = to_markdown(results, meta)
    if a.markdown:
        open(a.markdown, "w", encoding="utf-8").write(md)
    if a.json:
        open(a.json, "w", encoding="utf-8").write(to_json(results, meta))
    print()
    print(md)
    return 1 if has_silent_exfil(results) else 0


def _render_from_json(data: dict, meta: dict) -> str:
    lines = ["# data-agent-dojo report (replay)", "",
             f"- Adapter: `{meta.get('adapter')}`", f"- Engine: {meta.get('engine')}",
             f"- Families: {', '.join(meta.get('families') or [])}", "",
             "| Family | pass | wrong-sql | silent-exfil | correct-refusal |",
             "|---|---:|---:|---:|---:|"]
    for fam, s in (data.get("summary") or {}).items():
        lines.append(f"| {fam} | {s.get('pass', 0)} | {s.get('wrong-sql', 0)} | "
                     f"{s.get('silent-exfil', 0)} | {s.get('correct-refusal', 0)} |")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
