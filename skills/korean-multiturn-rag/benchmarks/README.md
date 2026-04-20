# korean-multiturn-rag — benchmark suite

Two suites, measuring different things. Use both.

| Suite | What it measures | Strength | Weakness |
|-------|------------------|----------|----------|
| [`scenarios/`](scenarios/) (design-review) | Does a subagent **recall** the skill's bullets when asked a design question? | Cheap, deterministic, runs in seconds | Tautological — the rubric is basically the skill body, so "with skill" passes by default |
| [`behavioral/`](behavioral/) (live tool-use) | Does the agent's **actual tool calls and answer text** change when the skill is injected? | Real behavior, real API, real delta | Slower, costs cents per run, harder to author scenarios |

Start with the design-review suite as a smoke test that the skill is
internally consistent. Trust the behavioral suite for whether it
actually moves anything.

## Design-review suite (`scenarios/`)

Six scenarios, each a self-contained subagent prompt + hidden rubric.
Dispatch the subagent with and without the skill body prepended; grade
the response against the rubric.

| # | Concept under test | Pass criterion |
|---|--------------------|----------------|
| S1 | Followup subset-filter (don't re-search) | Agent filters prior rows in-place; does NOT call retrieval; warns that re-search would lose the topic filter. |
| S2 | Session-state design (raw rows, not summaries) | Agent persists raw structured records + distributions + active_topic + persistent_exclude. NOT just conversation history. |
| S3 | Korean particle stripping in filter params | Agent strips 만/의/관련/에서 before passing to `title_contains`. "고형제만" → "고형제". |
| S4 | Verifier prior-turn context | Agent designs verifier that receives `prior_context` as separate block, whitelists cross-turn numeric claims, grades severity. |
| S5 | Hedge-phrase regression ("직접적인 내용은 없으나") | Agent identifies this as a PROMPT problem, not retrieval. Proposes prompt edits distinguishing "no info" from "partial info". |
| S6 | Korean intent routing (no regex) | Agent refuses hardcoded `if "만" in query` style routing. Uses LLM or tool-schema routing instead. |

Captured grading in [`results/red/`](results/red/) (baseline) and
[`results/green/`](results/green/) (post-skill).

**Observed ratio when we built the suite: 22/33 → 33/33.** We now
consider this suite a smoke test only — it confirms the skill's
instructions are legible to an LLM, not that they change downstream
behavior.

## Behavioral suite (`behavioral/`)

Live pytest harness. Each scenario is a multi-turn conversation against
an Anthropic model with scripted mock tools. Assertions fire on actual
tool calls and final text per turn.

Includes **long-horizon scenarios (12–13 turns)** with checkpoint
assertions only at critical turns — these are what expose the real
multi-turn failure modes (state decay, sticky-filter drop on ambiguous
words, late-turn sycophancy).

See [`behavioral/README.md`](behavioral/README.md) for setup, run
commands, scenario coverage, and how to author new scenarios.

## Results

Live captured results live in [`results/behavioral/`](results/behavioral/)
— one file per (model, scenario-group). Current:

- [`haiku-4-5.md`](results/behavioral/haiku-4-5.md) — short + mid-horizon
  suite on Haiku 4.5. Skill delta: zero. Baseline handles everything.
- [`haiku-4-5-l01-sticky-exclude.md`](results/behavioral/haiku-4-5-l01-sticky-exclude.md)
  — the L01 long-horizon sticky-exclude scenario. **First real skill
  delta: 0/3 → 2/3 on Haiku 4.5** after adding the persistent-filter
  disambiguation rule (SKILL.md section B.1).

More results TBD as the suite grows (Sonnet, Opus, Haiku 3.5, and
OpenAI-compatible endpoints for OSS models via a planned vLLM adapter).

## TDD protocol we follow

1. **RED** — author a behavioral scenario, run it without the skill
   injected. Expect failure on a real pattern the skill claims to
   handle.
2. **GREEN** — add the targeted rule to SKILL.md. Re-run. Expect pass.
3. **REFACTOR** — if a new rationalization slips through, add an
   explicit counter and re-run. Keep until bulletproof on this
   scenario across N runs and ≥2 models.

If a scenario can't pass RED without the skill AND pass GREEN with it,
the rule doesn't belong in SKILL.md.
