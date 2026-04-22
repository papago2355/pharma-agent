"""Direct n-run driver for the behavioral matrix.

Complements the pytest harness: the pytest version only asserts a
threshold and swallows the raw pass counts in the assertion message.
This driver writes:

  - results/<label>/results.json — full per-cell, per-run outcomes
  - results/<label>/summary.md    — markdown fragment with pass-rate table

Usage
-----
  export ANTHROPIC_API_KEY=...                 # if backend=anthropic
  # or
  export BENCHMARK_BACKEND=openai_compat
  export BENCHMARK_BASE_URL=http://localhost:8200/v1
  export BENCHMARK_API_KEY=EMPTY

  python run_matrix.py \
      --model <model_id> \
      --runs 10 \
      --scenarios l01 l02 l03 \
      --label <label-for-output-dir>

Each (scenario × skill_on × run_idx) cell runs a fresh multi-turn
conversation and grades every turn. A cell "passes" if all graded turns
pass.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path

import yaml

from grading import grade_run
from mocks import build_mock_handler
from runner import run_scenario


HERE = Path(__file__).parent
SCENARIO_DIR = HERE / "scenarios"
DEFAULT_SKILL_PATH = HERE.parent.parent / "SKILL.md"
RESULTS_DIR = HERE.parent / "results"  # benchmarks/results/<label>/, matches pre-existing green/red/behavioral subdirs


def _load_skill_body() -> str:
    """Skill body injected when skill_on=True.

    Override the source file via BENCHMARK_SKILL_FILE env var — either an
    absolute path or a filename relative to HERE.parent.parent (the skill
    root). Defaults to SKILL.md.
    """
    override = os.environ.get("BENCHMARK_SKILL_FILE")
    if override:
        p = Path(override)
        if not p.is_absolute():
            p = HERE.parent.parent / override
        path = p
    else:
        path = DEFAULT_SKILL_PATH
    text = path.read_text(encoding="utf-8")
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


def _load_scenario(sid: str) -> tuple[str, dict]:
    matches = sorted(SCENARIO_DIR.glob(f"{sid}_*.yaml")) + sorted(
        SCENARIO_DIR.glob(f"{sid}.yaml")
    )
    if not matches:
        raise SystemExit(f"No scenario file matching {sid!r} in {SCENARIO_DIR}")
    path = matches[0]
    return path.stem, yaml.safe_load(path.read_text(encoding="utf-8"))


def _run_cell(
    *,
    scenario_id: str,
    scenario: dict,
    skill_on: bool,
    run_idx: int,
    model: str,
) -> dict:
    """One full conversation + grade. Never raises; errors become a
    non-pass verdict with the exception recorded."""
    try:
        mock = build_mock_handler(scenario.get("mock", []))
        result = run_scenario(
            model=model,
            system=_system_prompt(scenario, skill_on),
            tools=scenario["tools"],
            mock_handler=mock,
            user_turns=[t["user"] for t in scenario["turns"]],
            skill_injected=skill_on,
        )
        verdicts = grade_run(result, scenario)
        failures = [
            {
                "turn_index": v.turn_index,
                "user_msg": v.user_msg,
                "failures": v.failures,
            }
            for v in verdicts
            if not v.passed
        ]
        passed = not failures
        return {
            "scenario": scenario_id,
            "skill_on": skill_on,
            "run_idx": run_idx,
            "passed": passed,
            "failures": failures,
            "error": None,
        }
    except Exception as exc:  # pragma: no cover — operational surface
        return {
            "scenario": scenario_id,
            "skill_on": skill_on,
            "run_idx": run_idx,
            "passed": False,
            "failures": [],
            "error": f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}",
        }


def _aggregate(cells: list[dict]) -> dict[str, dict[bool, dict]]:
    """{scenario_id: {skill_on_bool: {"pass": int, "total": int}}}"""
    agg: dict[str, dict[bool, dict]] = {}
    for c in cells:
        by_skill = agg.setdefault(c["scenario"], {})
        bucket = by_skill.setdefault(c["skill_on"], {"pass": 0, "total": 0})
        bucket["total"] += 1
        if c["passed"]:
            bucket["pass"] += 1
    return agg


def _summary_md(agg: dict, *, model: str, runs: int, label: str) -> str:
    lines = [
        f"# Behavioral benchmark — {label}",
        "",
        f"- Model: `{model}`",
        f"- Runs per cell: {runs}",
        "",
        "| Scenario | Baseline (no skill) | With skill |",
        "|---|:-:|:-:|",
    ]
    for sid in sorted(agg.keys()):
        baseline = agg[sid].get(False, {"pass": 0, "total": 0})
        skilled = agg[sid].get(True, {"pass": 0, "total": 0})
        lines.append(
            f"| **{sid}** "
            f"| {baseline['pass']}/{baseline['total']} "
            f"| {skilled['pass']}/{skilled['total']} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument(
        "--scenarios",
        nargs="+",
        default=["l01", "l02", "l03"],
        help="Scenario id prefixes to load (e.g. l01 s01).",
    )
    ap.add_argument(
        "--label",
        required=True,
        help="Subdirectory name under results/ for this matrix run.",
    )
    ap.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Parallel cells. Keep 1 when sharing a vLLM with production.",
    )
    args = ap.parse_args()

    scenarios = [_load_scenario(s) for s in args.scenarios]
    cells_to_run: list[dict] = []
    for sid, scenario in scenarios:
        for skill_on in (False, True):
            for run_idx in range(args.runs):
                cells_to_run.append(
                    dict(
                        scenario_id=sid,
                        scenario=scenario,
                        skill_on=skill_on,
                        run_idx=run_idx,
                        model=args.model,
                    )
                )

    print(
        f"[matrix] {len(cells_to_run)} cells to run "
        f"(scenarios={len(scenarios)}, conditions=2, runs={args.runs}) "
        f"concurrency={args.concurrency}",
        file=sys.stderr,
    )

    out_dir = RESULTS_DIR / args.label
    out_dir.mkdir(parents=True, exist_ok=True)

    cells: list[dict] = []
    t0 = time.time()
    if args.concurrency <= 1:
        for i, kwargs in enumerate(cells_to_run, start=1):
            cell = _run_cell(**kwargs)
            cells.append(cell)
            status = "PASS" if cell["passed"] else "FAIL"
            err = f" ERR={cell['error'][:80]}" if cell["error"] else ""
            print(
                f"[{i}/{len(cells_to_run)}] {cell['scenario']} "
                f"skill={cell['skill_on']} run={cell['run_idx']} "
                f"{status}{err}",
                file=sys.stderr,
                flush=True,
            )
    else:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            futs = {ex.submit(_run_cell, **kwargs): kwargs for kwargs in cells_to_run}
            done = 0
            for fut in as_completed(futs):
                cell = fut.result()
                cells.append(cell)
                done += 1
                status = "PASS" if cell["passed"] else "FAIL"
                err = f" ERR={cell['error'][:80]}" if cell["error"] else ""
                print(
                    f"[{done}/{len(cells_to_run)}] {cell['scenario']} "
                    f"skill={cell['skill_on']} run={cell['run_idx']} "
                    f"{status}{err}",
                    file=sys.stderr,
                    flush=True,
                )
    wall = time.time() - t0

    agg = _aggregate(cells)
    (out_dir / "results.json").write_text(
        json.dumps(
            {
                "model": args.model,
                "runs_per_cell": args.runs,
                "wall_time_seconds": wall,
                "cells": cells,
                "aggregate": {
                    sid: {str(k): v for k, v in per_cond.items()}
                    for sid, per_cond in agg.items()
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    summary_md = _summary_md(agg, model=args.model, runs=args.runs, label=args.label)
    (out_dir / "summary.md").write_text(summary_md, encoding="utf-8")

    print(file=sys.stderr)
    print(summary_md, file=sys.stderr)
    print(f"Wrote: {out_dir}/results.json", file=sys.stderr)
    print(f"Wrote: {out_dir}/summary.md", file=sys.stderr)
    print(f"Wall time: {wall:.1f}s", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
