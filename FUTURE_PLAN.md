# Future plan

Roadmap for what's next. Items 1–3 below are **shipped** — the docs exist in
`docs/{en,ko}/04-06` — and are kept here as a pointer so contributors can
find the motivation that produced them. Everything under **Next up** and
**Parking lot** is genuinely still to do.

---

## Shipped

These were on the roadmap and are now in the repo. Link + a one-line note
so the original scoping isn't lost.

- ✅ **Verifier cross-turn context** → [`docs/en/04-verifier-cross-turn.md`](docs/en/04-verifier-cross-turn.md) · [`ko`](docs/ko/04-verifier-cross-turn.md)
  — why stateless verifiers false-positive on multi-turn answers, and the
  `prior_context` block that fixes it.
- ✅ **Korean NLP gotchas for agentic RAG** → [`docs/en/05-korean-nlp-gotchas.md`](docs/en/05-korean-nlp-gotchas.md) · [`ko`](docs/ko/05-korean-nlp-gotchas.md)
  — particle stripping, hedge-phrase regression, dosage-form fallback,
  tokenizer variance.
- ✅ **Pharma-specific patterns** → [`docs/en/06-pharma-specific.md`](docs/en/06-pharma-specific.md) · [`ko`](docs/ko/06-pharma-specific.md)
  — QMS filter-first routing, SOP citation discipline, change-control chain,
  GMP-aware refusal formatting.
- ✅ **Inference-optimized SKILL.md rewrite (v2)** → promoted to
  [`skills/korean-multiturn-rag/SKILL.md`](skills/korean-multiturn-rag/SKILL.md).
  Converted the builder-facing field guide into imperative model-facing
  rules with Korean few-shots and a forced-restatement rule. On Gemma
  4 26B n=10 this flipped L01 (sticky exclude durability) from 0/10 to
  10/10. Old body preserved at `SKILL-v1-legacy.md`.

---

## Next up

Prioritized in the order I think they're most valuable to ship.

### 1. Three-condition ablation (the fair-comparison fix)

Highest-priority empirical gap. Current benchmark compares
`minimal_prompt` vs `minimal_prompt + skill_body`. That cannot
distinguish "Korean-specific patterns are the lever" from "any longer
thoughtful prompt helps." Fix with a three-condition matrix:

- **a — Baseline**: current minimal system prompt.
- **b — Generic guidance (length-matched)**: a prompt roughly matching
  the skill in word count, containing generic multi-turn agent rules
  (be careful about state, cite sources, don't hallucinate, clarify
  ambiguity) with **zero Korean-specific content** — no particle
  stripping, no sticky-filter table, no hedge-phrase rule.
- **c — Actual skill**: the current `SKILL.md` body.

Interpretation:
- `c > b > a`  → specificity matters; skill earns its claim.
- `c ≈ b > a`  → length is the lever; skill overclaims.
- `c > b ≈ a`  → very strong evidence skill content is doing the work.

Ship before making any "Korean patterns are the lever" claim in
marketing, talks, or docs beyond what's currently in README.

### 2. Mem0 / Zep / LangGraph memory ablation

Add a fourth condition using one off-the-shelf memory library
(Mem0 first, it has the simplest integration) as the memory layer
under baseline. If the skill still moves metrics over that, it
demonstrates the patterns are orthogonal to memory infrastructure —
the exact claim made in the README's "How this compares" section.

### 3. Richer mock retrieval content in scenarios

Current scenario mocks return thin structured rows (`{id, team, grade, ...}`)
which is the right shape for assertions on filter behavior. But the
scenarios would read as more "real" — and exercise the generation layer
— if mocks also included Korean paragraph-level document text and
source citations. Design this as a NEW scenario family (`s12_rich_mock_text.yaml`,
etc.) rather than rewriting existing L/S scenarios, so the filter-behavior
assertions keep their current precision.

### 4. Benchmark coverage for the patterns that aren't yet measured

The field guide covers ~6 patterns; only a subset has a behavioral scenario.
Write scenarios for:

- **Particle stripping under adversarial phrasing** (already has s02, but
  could be expanded to cover 만성/만료/만족/만약 homonym traps).
- **Hedge-phrase regression** on generation — assert the answer does NOT
  contain "직접적인 내용은 없으나" when partial info exists.
- **Verifier cross-turn** — add a scenario that runs a mock verifier and
  shows baseline false-positive vs. skill-guided pass.

### 5. Cross-model matrix

Current state: **Gemma 4 26B** via vLLM at n=10 for L01–L03 and n=5 for
L04 (the headline evidence); **Claude Haiku 4.5** n=3 on v1 skill only
(historical row). Still outstanding:

- **Qwen 3.5 35B FP8 via vLLM** (tool-call parser `qwen3_xml`
  confirmed working). Deferred from the Gemma session because of GPU
  contention with the production Gemma 4 service — schedule for a
  separate idle window when CKD is offline for maintenance.
- **Claude Haiku 4.5 rerun on the promoted v2 SKILL.md** — the v1
  result was 0/3 → 2/3; v2 should go materially higher.
- **Claude Sonnet 4.6** — stronger Anthropic baseline; where L04-T9
  might be solvable without any v3 rule change.
- **Weaker models** (Haiku 3.5, Qwen 7B) — should amplify the skill's
  effect if the patterns-vs-length-matched hypothesis from §1 holds.

### 6. n-run aggregation in the pytest harness

Currently `BENCHMARK_RUNS` + a threshold assertion only tells you pass/fail
per cell. Add a mode that emits per-cell pass rates (e.g. `7/10`) into a
results JSON so the README table can regenerate from a single command.

---

## Parking lot

Topics that might become their own docs later, or might fold into the above.

- **Prompt versioning & rollback**: how to promote `rag_prompts_v6.yaml`
  safely when `_vN+1` regresses on some slice.
- **Agent budget & dedup guard**: why dedup keys should include the
  observation hash, not just action+params.
- **Wiki-augmented agents**: when to let the agent consult a wiki page
  vs. embed the page into retrieval vs. hardcode the knowledge.
- **SSE contract design**: event types, ordering guarantees, what to do
  when the stream dies mid-answer.
- **Multi-recipe planning**: sop_search → qms_search handoff, when to
  switch, how to enrich the second recipe with the first's output.

---

## How to pick up a topic

1. Claim it by opening an issue titled "draft: <topic>".
2. Write the EN doc first. Don't translate line-by-line — write the KO
   version as natural Korean tech writing (keep English terms like LLM,
   ReAct, observation; translate verbs and nuance).
3. Pair each pattern with at least one concrete symptom you'd see in
   logs or a UI screenshot — not just abstract advice.
4. Open PR; reviewers check both languages for parity of depth, not
   word-for-word match.
