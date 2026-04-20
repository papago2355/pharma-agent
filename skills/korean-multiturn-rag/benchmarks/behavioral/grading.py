"""Grade a RunResult against a scenario's per-turn expectations.

Expectations per turn (all optional):
  tool_called:          name of expected tool, or null for "no tool call"
  tool_params_contain:  dict of substrings to check in the tool_input
  tool_params_absent:   list of substrings that must NOT appear in any param
  answer_contains:      list of substrings that must appear in final_text
  answer_not_contains:  list of substrings that must NOT appear
"""

from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass
class TurnVerdict:
    turn_index: int
    user_msg: str
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def _flatten_values(obj) -> list[str]:
    out: list[str] = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_flatten_values(v))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_flatten_values(v))
    elif obj is not None:
        out.append(str(obj))
    return out


def grade_turn(turn_result, expect: dict, idx: int) -> TurnVerdict:
    failures: list[str] = []

    # Tool call expectations
    if "tool_called" in expect:
        want = expect["tool_called"]
        called = [c["name"] for c in turn_result.tool_calls]
        if want is None and called:
            failures.append(f"expected no tool call, got {called}")
        elif want is not None and want not in called:
            failures.append(f"expected tool '{want}', got {called or 'none'}")

    if "tool_params_contain" in expect:
        want = expect["tool_params_contain"]
        ok = any(
            all(
                k in call["input"]
                and (str(v) in json.dumps(call["input"][k], ensure_ascii=False))
                for k, v in want.items()
            )
            for call in turn_result.tool_calls
        )
        if not ok:
            failures.append(
                f"no tool call matched params_contain={want}; calls={turn_result.tool_calls}"
            )

    if "tool_params_absent" in expect:
        forbidden = expect["tool_params_absent"]
        for call in turn_result.tool_calls:
            flat = _flatten_values(call["input"])
            for bad in forbidden:
                if any(bad in v for v in flat):
                    failures.append(
                        f"tool call {call['name']} contained forbidden substring '{bad}' "
                        f"in params {call['input']}"
                    )

    # Answer text expectations
    text = turn_result.final_text or ""
    for needle in expect.get("answer_contains", []):
        if needle not in text:
            failures.append(f"answer missing required substring '{needle}'")
    any_list = expect.get("answer_contains_any") or []
    if any_list and not any(n in text for n in any_list):
        failures.append(f"answer missing at least one of {any_list}")
    for bad in expect.get("answer_not_contains", []):
        if bad in text:
            failures.append(f"answer contained forbidden substring '{bad}'")

    return TurnVerdict(turn_index=idx, user_msg=turn_result.user_msg, failures=failures)


def grade_run(run_result, scenario: dict) -> list[TurnVerdict]:
    verdicts: list[TurnVerdict] = []
    for i, (turn_res, turn_spec) in enumerate(
        zip(run_result.turns, scenario["turns"])
    ):
        verdicts.append(grade_turn(turn_res, turn_spec.get("expect", {}), i))
    return verdicts
