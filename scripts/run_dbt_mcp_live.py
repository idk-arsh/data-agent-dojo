"""Live run: the dbt-mcp-show adapter against one or more families.

FREE models only. Gated behind DOJO_LIVE_DBT_MCP=1 and a key (file or env).
Writes a JSON + Markdown report. Example:

  DOJO_LIVE_DBT_MCP=1 DOJO_OPENROUTER_KEY_FILE=... \
  python scripts/run_dbt_mcp_live.py --families cell-value-injection \
      --model google/gemma-4-31b-it:free --out eval/dbt_mcp_live_2026-10-19
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_agent_dojo.adapters.dbt_mcp_show import DbtMcpShowAdapter
from data_agent_dojo.runner import Runner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--families", default="cell-value-injection")
    ap.add_argument("--model", default="google/gemma-4-31b-it:free")
    ap.add_argument("--max-calls", type=int, default=40)
    ap.add_argument("--only", default=None)
    ap.add_argument("--out", default="eval/dbt_mcp_live")
    a = ap.parse_args()

    families = [f.strip() for f in a.families.split(",") if f.strip()]
    adapter = DbtMcpShowAdapter(model=a.model, max_calls=a.max_calls)
    runner = Runner(adapter=adapter, engine_name="duckdb", families=families,
                    only=a.only.split(",") if a.only else None)

    print(f"LIVE dbt-mcp-show model={a.model} families={families}")
    results = runner.run()

    rows = []
    summary: dict[str, dict[str, int]] = {}
    for r in results:
        rows.append({"payload_id": r.payload_id, "family": r.family, "title": r.title,
                     "verdict": r.verdict.kind, "reason": r.verdict.reason,
                     "sql": r.verdict.observed_sql, "severity": r.severity})
        s = summary.setdefault(r.family, {"pass": 0, "wrong-sql": 0,
                                          "silent-exfil": 0, "correct-refusal": 0})
        s[r.verdict.kind] = s.get(r.verdict.kind, 0) + 1

    calls_used = getattr(adapter, "calls_used", None)
    meta = {"adapter": "dbt-mcp-show", "model": a.model, "engine": "duckdb",
            "families": families, "calls_used": calls_used}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out + ".json", "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "summary": summary, "rows": rows}, f, indent=2)
    print("calls_used:", calls_used)
    print("summary:", json.dumps(summary))
    print("wrote", a.out + ".json")


if __name__ == "__main__":
    main()
