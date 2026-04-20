# Haiku 4.5 — L01 Sticky-Exclude Durability (13 turns)

**Date:** 2026-04-20
**Model:** `claude-haiku-4-5`
**Scenario:** `l01_long_sticky_exclude_durability` (13 turns, 4 checkpoint
assertions at T1, T2, T8, T12)
**Runs per cell:** 3, pass threshold: 2/3
**Cost:** ~$0.30 per full run

## The scenario in one paragraph

User asks for deviation records (T1), sets a persistent exclude "바이오
부서는 제외" (T2), goes through 5 filter/topic-shift turns (T3–T7),
asks to see "이번 달 전체 기록" (T8 — the trap turn), continues with
stats/subset queries (T9–T11), then explicitly revokes the exclude
with "이번엔 바이오도 포함해서" (T12). The sticky exclude MUST survive
T3–T11 and drop cleanly at T12.

## Result

| Condition | Result | Note |
|-----------|:-:|------|
| no_skill (baseline) | **0/3 FAIL** | Sticky exclude drops at T8 when user says "전체 기록". Bio records silently reappear. |
| with_skill (patched) | **2/3 PASS** | Persistent-filter-disambiguation rule keeps the exclude active through T8; revoke at T12 works. |

**Skill delta: +2 runs (0/3 → 2/3).** First cell in our entire behavioral
suite where the skill flipped a RED to a GREEN.

## What was wrong before the patch

Baseline transcript showed a clean failure pattern:

- **T1** agent retrieves 20 records (bio included). ✓
- **T2** agent filters out bio records. ✓
- **T3–T7** agent applies subsequent filters and topic shifts; bio stays excluded. ✓
- **T8** user says: `다시 일탈 이야기로 돌아가서, 이번 달 전체 기록 다시 보여줘`
  → agent interprets **"전체"** as "unfiltered everything" and **silently drops the exclude**.
  Bio records reappear. User has no idea the filter was dropped.
- **T9–T11** subsequent operations run on the unfiltered set. Bio leaks.
- **T12** user explicitly says "바이오도 포함해서" and agent correctly
  includes bio. (Explicit revoke works; only the ambiguous one fails.)

Root cause: the skill's original `persistent_exclude` rule said "sticky
until user explicitly revokes" but did NOT define what counts as an
explicit revoke. Haiku treated "전체" as implicit revoke.

## The patch

Added a new section `B.1 Persistent-filter disambiguation` to
`SKILL.md` with a three-bucket classification:

- **AMBIGUOUS** (전체, 모두, 다시, 새로, 전부 다시, …) → KEEP filter, mention it
- **Subset filter** (그 중 X만, X 위주로) → compose WITH the filter
- **EXPLICIT revoke** (X도 포함, X 필터 해제, 필터 없이) → DROP filter

Plus four hard rules:

1. Never silently drop a persistent filter.
2. Default to KEEP on ambiguity.
3. Always restate the active filter in the answer.
4. Subset operations compose with persistent filters — don't replace them.

See [`SKILL.md`](../../../SKILL.md) section B.1 for the full text.

## What this proves

This is the first piece of behavioral evidence that the skill body can
meaningfully shape an agent's long-horizon behavior when the rule is
**specific enough**. Previous attempts with abstract guidance ("sticky
until revoked") produced zero measurable delta. The concrete
three-bucket classification with Korean phrasings enumerated produced
a clean +2/3 lift.

## What it does NOT prove

- **N=3, single scenario.** We need more cases and more runs to
  generalize.
- **Only on Haiku 4.5.** Larger models might not need this rule (they
  may handle "전체" correctly natively); smaller models might need an
  even more prescriptive version.
- **The rule is targeted.** We may have "taught to the test." The
  honest next step is to design a separate sticky-filter scenario with
  a different ambiguous trigger (e.g., "초기화", "새 결과") and
  re-run to check generalization.

## More results coming — TBD

This file covers **L01 only.** The full long-horizon benchmark suite
currently includes three 12+ turn scenarios; L02 (referential decay)
and L03 (late contradiction pushback) both pass the baseline on Haiku
4.5, so no before/after delta to report. As we add harder scenarios
and test across a model matrix (Sonnet 4.6, Haiku 3.5, and an
OpenAI-compatible vLLM for Gemma/Qwen-class open models), further
result files will land in this directory:

- `haiku-4-5.md` — short + mid-horizon suite on Haiku 4.5 (existing)
- `haiku-4-5-l01-sticky-exclude.md` — this file
- `sonnet-4-6.md` — TBD
- `haiku-3-5.md` — TBD
- `vllm-<model>.md` — TBD, pending OpenAI-compatible adapter

## How to reproduce

```bash
cd skills/korean-multiturn-rag/benchmarks/behavioral
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
BENCHMARK_MODEL=claude-haiku-4-5 BENCHMARK_RUNS=3 BENCHMARK_PASS_THRESHOLD=2 \
  pytest test_behavioral.py -v -k "l01"
```

## Raw pytest output

```
============================= test session starts ==============================
collected 28 items / 26 deselected / 2 selected

test_behavioral.py::test_scenario[no_skill-l01_long_sticky_exclude_durability-scenario0] FAILED
test_behavioral.py::test_scenario[with_skill-l01_long_sticky_exclude_durability-scenario0] PASSED

=================================== FAILURES ===================================
AssertionError: l01_long_sticky_exclude_durability skill_on=False: passed only 0/3 runs (threshold=2).

============ 1 failed, 1 passed, 26 deselected in 313.47s (0:05:13) ============
```
