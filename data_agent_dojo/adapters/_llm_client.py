"""Minimal OpenAI-compatible tool-calling client for the live adapters.

Reads an OpenRouter key from the environment or from the paper harness's key
file convention (a sibling `.openrouter-key` file pointed at by DOJO_OPENROUTER_KEY_FILE).
Only free models should be passed in by the caller; this module does not choose
a model. It never logs the key.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable

OPENROUTER_BASE = "https://openrouter.ai/api/v1"
KEY_ENVS = ("DOJO_OPENROUTER_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")
KEY_FILE_ENV = "DOJO_OPENROUTER_KEY_FILE"


def read_key() -> str | None:
    for k in KEY_ENVS:
        v = os.environ.get(k)
        if v and v.strip():
            return v.strip()
    path = os.environ.get(KEY_FILE_ENV)
    if path and os.path.isfile(path):
        txt = open(path, encoding="utf-8").read().strip()
        return txt or None
    return None


def available() -> bool:
    return read_key() is not None


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    call_id: str


@dataclass
class LLMResult:
    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    calls_used: int = 0


class FreeModelClient:
    """Thin wrapper over an OpenAI-compatible chat/completions endpoint."""

    def __init__(self, model: str, max_calls: int = 40):
        from openai import OpenAI
        key = read_key()
        if not key:
            raise RuntimeError("no OpenRouter key found; set DOJO_OPENROUTER_KEY or the key file")
        self._client = OpenAI(base_url=OPENROUTER_BASE, api_key=key)
        self.model = model
        self.max_calls = max_calls
        self.calls_used = 0

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             temperature: float = 0.0) -> Any:
        import time
        from openai import RateLimitError, APIStatusError
        if self.calls_used >= self.max_calls:
            raise RuntimeError(f"call budget of {self.max_calls} exhausted")
        self.calls_used += 1
        kw: dict[str, Any] = dict(model=self.model, messages=messages, temperature=temperature)
        if tools:
            kw["tools"] = tools
            kw["tool_choice"] = "auto"
        last: Exception | None = None
        for attempt in range(4):
            try:
                return self._client.chat.completions.create(**kw)
            except (RateLimitError, APIStatusError) as e:  # transient upstream 429/5xx
                last = e
                code = getattr(e, "status_code", None)
                if code not in (429, 500, 502, 503):
                    raise
                time.sleep(3 * (attempt + 1))
        raise last  # type: ignore[misc]
