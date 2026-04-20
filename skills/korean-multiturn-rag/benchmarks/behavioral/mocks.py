"""Declarative mock tool handler built from a scenario's `mock` section.

A scenario declares a list of `{when, returns}` entries. `when` is matched
against the tool call by name + param substrings. The first match wins.
Everything else returns an empty-results payload so the agent must handle
zero-result honestly rather than assume a fallback.

Matching stays intentionally dumb (substring) — we do NOT want the mock
to quietly interpret morphology the way a real retriever might. The
agent's job is to strip particles before it calls the tool; the mock
rewards it only if it actually did.
"""

from __future__ import annotations

import json
from typing import Any


def _param_match(actual: Any, expected: Any) -> bool:
    """Loose-equality match suitable for mock routing.

    - dict:  every key in `expected` must be present in `actual` and recurse.
    - list:  every item in `expected` must be present in `actual` (order-
             independent, substring-tolerant for strings).
    - str:   substring check (expected in actual).
    - other: equality.
    """
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        return all(k in actual and _param_match(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return False
        for want in expected:
            if not any(_param_match(a, want) for a in actual):
                return False
        return True
    if isinstance(expected, str):
        return isinstance(actual, str) and expected in actual
    return actual == expected


def build_mock_handler(mock_rules: list[dict[str, Any]], empty_payload: dict[str, Any] | None = None):
    """Return a callable (tool_name, tool_input) -> content_json_string.

    `mock_rules` items look like:
        {
          "tool": "search_deviations",
          "when": {"query": "원료 이물"},
          "returns": {"records": [...], "total": 11, ...}
        }
    """
    default_empty = empty_payload or {"records": [], "total": 0}

    def handler(tool_name: str, tool_input: dict[str, Any]) -> str:
        for rule in mock_rules:
            if rule.get("tool") and rule["tool"] != tool_name:
                continue
            when = rule.get("when", {})
            if _param_match(tool_input, when):
                return json.dumps(rule["returns"], ensure_ascii=False)
        return json.dumps(default_empty, ensure_ascii=False)

    return handler
