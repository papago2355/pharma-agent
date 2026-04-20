"""pytest driver for behavioral Korean multi-turn benchmarks.

Usage
-----
  pip install anthropic pyyaml pytest
  export ANTHROPIC_API_KEY=...
  pytest benchmarks/behavioral/ -v
  pytest benchmarks/behavioral/ -v --skill=on   # inject SKILL.md body
  pytest benchmarks/behavioral/ -v -k s01       # one scenario

The test parametrizes over (scenario × skill_injected × run_index). Each
cell runs a full multi-turn conversation against a real Anthropic model
with scripted mock tools, then grades every turn. A cell passes if every
turn's verdict has zero failures.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from mocks import build_mock_handler
from grading import grade_run
from runner import run_scenario


HERE = Path(__file__).parent
SCENARIO_DIR = HERE / "scenarios"
SKILL_PATH = HERE.parent.parent / "SKILL.md"
MODEL = os.environ.get("BENCHMARK_MODEL", "claude-sonnet-4-6")
RUNS_PER_CELL = int(os.environ.get("BENCHMARK_RUNS", "3"))
PASS_THRESHOLD = int(os.environ.get("BENCHMARK_PASS_THRESHOLD", "2"))  # out of RUNS_PER_CELL


def _load_scenarios():
    files = sorted(list(SCENARIO_DIR.glob("s*.yaml")) + list(SCENARIO_DIR.glob("l*.yaml")))
    return [(f.stem, yaml.safe_load(f.read_text(encoding="utf-8"))) for f in files]


def _load_skill_body() -> str:
    text = SKILL_PATH.read_text(encoding="utf-8")
    # Strip YAML frontmatter
    if text.startswith("---"):
        _, _, rest = text.split("---", 2)
        return rest.strip()
    return text


def _system_prompt(scenario: dict, skill_on: bool) -> str:
    base = scenario["system_prompt"]
    if not skill_on:
        return base
    return (
        f"{base}\n\n"
        f"# Reference skill — korean-multiturn-rag\n\n"
        f"{_load_skill_body()}"
    )


@pytest.mark.parametrize("scenario_id,scenario", _load_scenarios())
@pytest.mark.parametrize("skill_on", [False, True], ids=["no_skill", "with_skill"])
def test_scenario(scenario_id, scenario, skill_on, request):
    passes = 0
    all_failures: list[str] = []
    for run_idx in range(RUNS_PER_CELL):
        mock = build_mock_handler(scenario.get("mock", []))
        result = run_scenario(
            model=MODEL,
            system=_system_prompt(scenario, skill_on),
            tools=scenario["tools"],
            mock_handler=mock,
            user_turns=[t["user"] for t in scenario["turns"]],
            skill_injected=skill_on,
        )
        verdicts = grade_run(result, scenario)
        if all(v.passed for v in verdicts):
            passes += 1
        else:
            for v in verdicts:
                if not v.passed:
                    all_failures.append(
                        f"[run {run_idx} turn {v.turn_index} '{v.user_msg[:30]}']: "
                        + "; ".join(v.failures)
                    )
    assert passes >= PASS_THRESHOLD, (
        f"{scenario_id} skill_on={skill_on}: "
        f"passed only {passes}/{RUNS_PER_CELL} runs (threshold={PASS_THRESHOLD}).\n"
        + "\n".join(all_failures[:20])
    )
