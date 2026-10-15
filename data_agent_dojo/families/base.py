"""Family interface. One attack family is one source of injected content.

A family exposes a list of Payload objects. Each payload is enough information
for the runner to: (a) prepare the fixture so the injection vector is present,
(b) ask the agent a benign question that the clean fixture answers correctly,
(c) classify what the agent did via the oracle's ExpectedShape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Literal, Protocol

from ..oracle import ExpectedShape

InjectionVector = Literal[
    "cell-value",
    "retrieved-document",
    "mcp-tool-description",
    "schema-comment",
    "error-message",
]

Severity = Literal["low", "medium", "high", "critical"]
DisclosureStatus = Literal["public", "embargoed", "fixture-only"]


@dataclass
class Payload:
    id: str
    family: str
    title: str
    description: str
    question: str
    injected_content: str
    injection_vector: InjectionVector
    expected_shape: ExpectedShape
    cve_refs: tuple[str, ...] = ()
    canaries: tuple[str, ...] = ()
    severity: Severity = "high"
    disclosure_status: DisclosureStatus = "fixture-only"
    fixture_hint: dict = field(default_factory=dict)


class FamilyBase(Protocol):
    name: str
    description: str

    def payloads(self) -> Iterable[Payload]: ...

    def expected_shape(self, payload: Payload) -> ExpectedShape: ...
