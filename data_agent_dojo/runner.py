"""Orchestrates one dojo run: for each selected payload, plant the injection,
drive the adapter, score the observation, collect a verdict.
"""
from __future__ import annotations

import os
import secrets
import tempfile
from dataclasses import dataclass, field

from .adapters.base import AdapterBase
from .engines import build_engine
from .families import FAMILIES, get as get_family
from .families.base import Payload
from .oracle import Verdict, judge


@dataclass
class RunResult:
    payload_id: str
    family: str
    title: str
    verdict: Verdict
    severity: str
    cve_refs: tuple[str, ...] = ()


@dataclass
class Runner:
    adapter: AdapterBase
    engine_name: str = "duckdb"
    dsn: str | None = None
    families: list[str] = field(default_factory=lambda: ["cell-value-injection"])
    only: list[str] | None = None
    log = staticmethod(print)

    def _payloads(self) -> list[Payload]:
        out: list[Payload] = []
        for name in self.families:
            fam = get_family(name)
            out.extend(fam.payloads())
        if self.only:
            out = [p for p in out if any(sub in p.id for sub in self.only)]
        return out

    def run(self) -> list[RunResult]:
        engine = build_engine(self.engine_name, self.dsn)
        root = tempfile.mkdtemp(prefix="dojo-")
        try:
            engine.build(root)
            self.adapter.setup(root)
            results: list[RunResult] = []
            for i, p in enumerate(self._payloads()):
                nonce = secrets.token_hex(2)
                workdir = os.path.join(root, f"p{i:02d}-{nonce}")
                fixture = engine.prepare(workdir, p.injected_content, p.canaries)
                try:
                    run = self.adapter.run(
                        p.question,
                        tool_result_override={
                            "injected_content": p.injected_content,
                            "canaries": p.canaries,
                            "allowed_table": next(iter(p.expected_shape.allowed_tables)),
                        },
                    )
                    touched = list(run.touched_resources) + engine.observe_resources(fixture)
                    run.touched_resources = touched
                    v = judge(run.to_observation(), p.expected_shape, p.canaries)
                finally:
                    engine.cleanup(fixture)
                r = RunResult(p.id, p.family, p.title, v, p.severity, p.cve_refs)
                results.append(r)
                Runner.log(f"  {v.kind:<16} {r.payload_id}  ({v.reason})")
            return results
        finally:
            try:
                self.adapter.teardown()
            finally:
                engine.close()


def available_families() -> list[str]:
    return sorted(FAMILIES)
