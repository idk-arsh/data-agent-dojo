"""Per-family four-way breakdown. No aggregate score.

Each family gets its own row of {pass, wrong-sql, silent-exfil, correct-refusal}
counts. Readers compare rows across adapters, not a scalar. silent-exfil for a
family is the primary number to watch; correct-refusal shows whether the agent
knew the injection was there.
"""
from __future__ import annotations

import json
from collections import Counter
from typing import Iterable

from .runner import RunResult

VERDICT_KINDS = ("pass", "wrong-sql", "silent-exfil", "correct-refusal")


def summary(results: Iterable[RunResult]) -> dict[str, dict[str, int]]:
    rs = list(results)
    by: dict[str, Counter] = {}
    for r in rs:
        by.setdefault(r.family, Counter())[r.verdict.kind] += 1
    out = {}
    for fam, counts in by.items():
        out[fam] = {k: counts.get(k, 0) for k in VERDICT_KINDS}
    return out


def to_json(results: list[RunResult], meta: dict) -> str:
    rows = []
    for r in results:
        rows.append({
            "payload_id": r.payload_id,
            "family": r.family,
            "title": r.title,
            "verdict": r.verdict.kind,
            "reason": r.verdict.reason,
            "observed_sql": r.verdict.observed_sql,
            "touched_resources": r.verdict.touched_resources,
            "canary_touched": r.verdict.canary_touched,
            "severity": r.severity,
            "cve_refs": list(r.cve_refs),
        })
    return json.dumps({**meta, "summary": summary(results), "results": rows}, indent=2)


def to_markdown(results: list[RunResult], meta: dict) -> str:
    lines = [
        "# data-agent-dojo report",
        "",
        f"- Adapter: `{meta.get('adapter')}`",
        f"- Engine: {meta.get('engine')}",
        f"- Families: {', '.join(meta.get('families', []))}",
        "",
        "No single aggregate score is reported. Compare per-family rows across adapters.",
        "",
        "| Family | pass | wrong-sql | silent-exfil | correct-refusal |",
        "|---|---:|---:|---:|---:|",
    ]
    for fam, s in summary(results).items():
        lines.append(f"| {fam} | {s['pass']} | {s['wrong-sql']} | {s['silent-exfil']} | {s['correct-refusal']} |")
    lines += [
        "",
        "`silent-exfil` is the primary security event: the agent produced SQL (or returned text) outside the payload's declared shape.",
        "",
        "| Verdict | Payload | Family | Reason |",
        "|---|---|---|---|",
    ]
    order = {"silent-exfil": 0, "wrong-sql": 1, "pass": 2, "correct-refusal": 3}
    for r in sorted(results, key=lambda r: order.get(r.verdict.kind, 9)):
        lines.append(f"| {r.verdict.kind} | `{r.payload_id}` | {r.family} | {_cell(r.verdict.reason)} |")
    return "\n".join(lines) + "\n"


def _cell(s: str, n: int = 120) -> str:
    s = " ".join((s or "").split())
    s = s if len(s) <= n else s[: n - 1] + "…"
    return s.replace("|", "\\|")


def has_silent_exfil(results: Iterable[RunResult]) -> bool:
    return any(r.verdict.kind == "silent-exfil" for r in results)
