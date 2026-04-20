# korean-multiturn-rag benchmark suite

TDD harness for the `korean-multiturn-rag` skill. Each scenario is a
self-contained subagent prompt that tests ONE concept the skill is supposed
to teach. The subagent receives only the scenario — no code, no hints,
no skill. We compare behavior **without** vs **with** the skill.

## The six scenarios

| # | Concept under test | Pass criterion |
|---|--------------------|----------------|
| S1 | Followup subset-filter (don't re-search) | Agent filters prior rows in-place; does NOT call retrieval; warns that re-search would lose the topic filter. |
| S2 | Session-state design (raw rows, not summaries) | Agent persists raw structured records + distributions + active_topic + persistent_exclude. NOT just conversation history. |
| S3 | Korean particle stripping in filter params | Agent strips 만/의/관련/에서 before passing to `title_contains`. "고형제만" → "고형제". |
| S4 | Verifier prior-turn context | Agent designs verifier that receives `prior_context` as separate block, whitelists cross-turn numeric claims, grades severity. |
| S5 | Hedge-phrase regression ("직접적인 내용은 없으나") | Agent identifies this as a PROMPT problem, not retrieval. Proposes prompt edits distinguishing "no info" from "partial info". |
| S6 | Korean intent routing (no regex) | Agent refuses hardcoded `if "만" in query` style routing. Uses LLM or tool-schema routing instead. |

## Pass/fail grading

Each scenario has an explicit **rubric** listing the ≥3 concrete behaviors
the answer must exhibit to pass. Missing any = FAIL. No partial credit —
the skill either teaches the agent correctly or it doesn't.

## Protocol

1. **RED**: dispatch all 6 scenarios as general-purpose subagents WITHOUT
   the skill. Record verbatim rationalizations. Expected: multiple FAILs.
2. **GREEN**: write `SKILL.md` targeting the specific failures observed.
   Dispatch all 6 scenarios WITH the skill injected into the prompt.
   Expected: all PASS.
3. **REFACTOR**: any new rationalization that emerges → add explicit
   counter. Re-run until bulletproof.

## Files

- `scenarios/S{1..6}-*.md` — scenario prompt + rubric
- `results/red/` — baseline outputs
- `results/green/` — post-skill outputs
- `results/summary.md` — rubric checkmarks per scenario per round
