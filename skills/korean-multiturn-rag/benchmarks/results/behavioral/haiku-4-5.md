# Behavioral benchmark — Haiku 4.5 live results

**Date:** 2026-04-20
**Model:** `claude-haiku-4-5`
**Runs per cell:** 3, pass threshold: 2/3
**Matrix:** 3 scenarios × {no_skill, with_skill} = 6 cells
**Total wall time:** 145.85 s
**Total cost:** ≈ $0.13

## Result table

| Scenario | no_skill | with_skill | Delta |
|----------|:-:|:-:|:-:|
| S01 pharma subset filter | **0/3 PASS** (FAIL) | **3/3 PASS** | **+3** |
| S02 pharma adversarial particle ("만성질환") | 3/3 PASS | 3/3 PASS | 0 |
| S03 cross-domain subset via "중에서…위주로" | 3/3 PASS | 3/3 PASS | 0 |

**Skill effect is real but narrow on Haiku 4.5.** Only one of three
scenarios shows a measurable with/without delta. Two of three pass in
both conditions — the baseline model already handles those patterns
from general capability.

## What actually failed on S01 no_skill

The baseline Haiku got the **hard** behaviors right without the skill:

- **Turn 1** correctly called `search_deviations(query="원료 이물", ...)`
  with `관련` particle stripped from the query. ✓
- **Turn 2** (`고형제만 추려줘`) **did not re-call** the tool
  (`tool_calls: []`), filtered the prior rows in place, and produced
  the correct 7 solid-dosage records (DEV-001, 002, 003, 006, 008, 009,
  011). ✓

The failing assertion was the softer one:

```
answer_contains_any: ["11건", "총 11"]
```

The baseline answer jumped straight to "총 7건" for the filtered subset
without restating the prior total ("원래 11건 중 고형제 7건"). The skill's
rule about quoting prior distributions / totals as anti-hallucination
scaffolding is what the with-skill runs reliably follow. Without the
skill, the model takes a terser path that's still *behaviorally*
correct but loses the explicit provenance link to the prior turn.

### no_skill turn 2 transcript (representative)

```
tool_calls: []
final_answer:
고형제(정제, 캡슐, 과립 등) 관련 원료 이물 일탈만 추려드렸습니다.
## 고형제 원료 이물 관련 일탈
| ID | 제목 | 등급 | 담당팀 | 상태 |
| DEV-001 | A정 10mg 원료 이물 발견 | Major | 생산1팀 | 종결 |
| DEV-002 | B캡슐 5mg 원료 이물 혼입 | Major | 생산1팀 | 종결 |
| DEV-003 | C정 20mg 원료 이물 확인 | Minor | 생산2팀 | 진행 중 |
| DEV-006 | F정 25mg 원료 이물 혼입 | Minor | 생산1팀 | 종결 |
| DEV-008 | H정 1mg 원료 이물 발견 | Major | 생산2팀 | 종결 |
| DEV-009 | I캡슐 100mg 원료 이물 혼입 | Minor | 생산2팀 | 종결 |
| DEV-011 | K과립 5g 원료 이물 확인 | Minor | 생산1팀 | 종결 |
### 요약:
- 총 7건
- Major 등급: 3건 (DEV-001, 002, 008)
- Minor 등급: 4건
```

Correct filtering, correct row set, no tool re-call. No mention of the
prior 11-row total. That's the failing assertion.

## Honest interpretation

1. **The design-review benchmark overstated the skill's behavioral
   effect.** That suite showed 67% → 100% because the scenarios
   measured *recall of skill bullets*. This suite measures *actual
   tool-use and answer behavior*, and the delta is much smaller.

2. **Frontier LLMs in 2026 already internalize the hard patterns.**
   Haiku 4.5 correctly decided not to re-retrieve on a Korean subset
   followup without any guidance. It correctly stripped the 관련
   particle. It correctly handled an adversarial `만성` query
   (S02) and a subset phrased with 중에서/위주로 (S03).

3. **The skill's measurable effect on Haiku is a style/safety layer**,
   not a behavior-changing intervention: it reliably makes the model
   quote prior totals and distributions, which matters for
   auditability and user trust in a regulated or multi-turn analytical
   setting, but does not change whether the model re-retrieves.

4. **Two reasons to still keep the skill despite the narrow delta:**
   - **Smaller / older / non-Claude models** likely show a bigger
     delta. The "don't re-retrieve on subset" behavior Haiku 4.5
     handles natively may not hold on GPT-4o-mini, Haiku 3.5, Qwen
     2.5 Instruct, or a 7B Korean-tuned open model.
   - **The scenarios in this suite are easy.** Harder scenarios we
     haven't written yet — sticky-exclude over 4+ turns, topic shift
     disguised as subset ("그럼 다른 약은?"), analytical followups
     requiring prior distribution reuse — are where the skill's
     deeper patterns would likely show a clear delta.

## What this result does NOT say

- It does NOT say the skill is useless. It says the skill's value on
  frontier Haiku, on these three specific scenarios, is concentrated
  in provenance/restatement rather than tool-use choice.
- It does NOT generalize to other models. Running the same matrix on
  Sonnet 4.6, Opus 4.7, or non-Claude models would produce different
  curves — likely smaller delta on bigger models, larger delta on
  smaller models.
- It does NOT prove the skill doesn't help on harder scenarios. S02
  and S03 passed the baseline because the mock behavior is clean and
  the rubric is focused. More adversarial scenarios would likely
  differentiate.

## Next steps to strengthen the evidence

1. **Harder scenarios** that the baseline can fail on:
   - Sticky exclude over 4+ turns (does the agent carry "바이오 제외"
     from turn 2 into turn 5's unrelated subset?).
   - Topic shift disguised as subset ("그럼 다른 약은?" — must re-
     retrieve, but baseline might treat as subset).
   - Analytical followup ("가장 빈번한 품목은?") where skill's
     `last_distributions` persistence should show clearer effect.
2. **Model matrix**: rerun on Sonnet 4.6, Opus 4.7, Haiku 3.5 to see
   how the delta scales with model capability.
3. **Larger N**: 5 or 10 runs per cell to tighten confidence intervals
   (current N=3 with pass threshold 2 is permissive).
4. **Live Korean production traces** (redacted) replayed through the
   same harness — real user phrasings will surface patterns the
   scripted scenarios miss.

## How to reproduce

```bash
cd benchmarks/behavioral
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
BENCHMARK_MODEL=claude-haiku-4-5 BENCHMARK_RUNS=3 BENCHMARK_PASS_THRESHOLD=2 \
  pytest test_behavioral.py -v
```

## Raw pytest summary

```
============================= test session starts ==============================
collected 6 items

test_behavioral.py::test_scenario[no_skill-s01_pharma_subset_filter-scenario0] FAILED
test_behavioral.py::test_scenario[no_skill-s02_pharma_adversarial_particle-scenario1] PASSED
test_behavioral.py::test_scenario[no_skill-s03_support_subset_no_particle-scenario2] PASSED
test_behavioral.py::test_scenario[with_skill-s01_pharma_subset_filter-scenario0] PASSED
test_behavioral.py::test_scenario[with_skill-s02_pharma_adversarial_particle-scenario1] PASSED
test_behavioral.py::test_scenario[with_skill-s03_support_subset_no_particle-scenario2] PASSED

AssertionError: s01_pharma_subset_filter skill_on=False: passed only 0/3 runs
  [run 0 turn 1 '고형제만 추려줘']: answer missing at least one of ['11건', '총 11']
  [run 1 turn 1 '고형제만 추려줘']: answer missing at least one of ['11건', '총 11']
  [run 2 turn 1 '고형제만 추려줘']: answer missing at least one of ['11건', '총 11']

=================== 1 failed, 5 passed in 145.85s (0:02:25) ====================
```
