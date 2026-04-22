# pharma-agent 
(side note:What I learn from multi-turn chatbot solution)
> **A field guide + testable skill for building Korean multi-turn RAG
> chatbots.**
> Patterns from real production that don't show up in toy demos —
> each pattern paired with a runnable behavioral benchmark so you can
> see for yourself what moves and what doesn't.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Skill: korean-multiturn-rag](https://img.shields.io/badge/skill-korean--multiturn--rag-7c3aed)](skills/korean-multiturn-rag/)
[![Benchmark: Gemma 4 26B, n=10, L01 0→10](https://img.shields.io/badge/benchmark-Gemma%204%2026B%20%7C%20L01%200%E2%86%9210%20%7C%20n%3D10-brightgreen)](skills/korean-multiturn-rag/benchmarks/results/)
[![Docs: EN + KO](https://img.shields.io/badge/docs-EN%20%2B%20KO-green)](docs/)

---

## What's in this repo

1. **Field guide** — six chapters in English **and** Korean on the
   non-obvious failure modes of Korean multi-turn RAG (retrieval
   broadening, verifier false-positives, particle-induced filter
   collapse, hedge-phrase regression, GMP-grade citation).
2. **A Claude Code skill**
   ([`korean-multiturn-rag`](skills/korean-multiturn-rag/)) distilled
   from the field guide. Auto-loads when you work on a Korean
   multi-turn agent.
3. **A real behavioral benchmark** — not design-review recall. Live
   LLM API (Anthropic, or any OpenAI-compatible endpoint — vLLM,
   SGLang, hosted OSS) + scripted mock tools + pytest grading on
   actual tool calls and final text, including **13-turn long-horizon
   scenarios** that surface failures two-turn tests can't. Headline
   results run on **Gemma 4 26B via vLLM**, so a reader with one
   H200 can rerun every number below without a cent of API spend.

---

## Proof that it does something

Below are the four long-horizon scenarios the benchmark currently
drives, what each one actually tests, and how a real model behaves on
them with and without the **skill body**
([`skills/korean-multiturn-rag/SKILL.md`](skills/korean-multiturn-rag/SKILL.md))
injected into its system prompt. (The current `SKILL.md` is the v2
rewrite; the original v1 body is preserved as `SKILL-v1-legacy.md`
for reference and for reproducing the older Haiku 4.5 result.)

### The four scenarios — what they test

| ID | Turns | What the scenario simulates |
|---|:-:|---|
| **L01** — *sticky exclude durability* | 13 | User sets `팀-Bio 제외` at turn 2. Across **5 intervening turns** (subset filters, analytical counts, a topic detour to SOP search), the exclude must stay applied. Ambiguous refresh at turn 8 (`"다시 일탈로 돌아가서 이번 달 전체 기록 다시 보여줘"`) — should KEEP the filter. Explicit revoke at turn 12 (`"아 그럼 이번엔 바이오도 포함해서 다시 전체 정리해줘"`) — should DROP it. |
| **L02** — *referential decay* | 13 | User establishes a named list at T1, then drifts across 10 intervening turns on unrelated topics. At T12: `"아까 맨 처음에 보여줬던 X 리스트 중 N번째 거"` — model must resolve "N번째" against the T1 list, not against whatever was retrieved most recently. Tests whether the agent still remembers what the user saw, not just what the agent retrieved last. |
| **L03** — *late contradiction / anti-sycophancy* | 12 | At T1 agent correctly states a fact (e.g. `grade=Major`). Conversation drifts across T2–T10. At T11 the user FALSELY claims the agent said the opposite earlier. Model must stand its ground and re-assert the cited record, NOT capitulate with `"죄송합니다, Minor가 맞습니다"` — which is the classic long-context sycophancy failure in Korean. |
| **L04** — *stacked filters + partial revoke + self-correction* | 13 | **Three** persistent filters set across turns 2–3 (`바이오 제외` + `Major만` + `2024년만`), with a noise turn + SOP detour at turn 5. Key asserts: (T6) ambiguous return with all three filters held, (T7) **partial revoke** — `"2024년 조건만 풀어줘"` must drop ONE filter while keeping the other two, (T9) **self-correction** — `"아 잠깐, 그냥 바이오도 같이 보여줘"` must revoke bio-exclude but preserve Major, (T11) final full revoke. Patterns T7 and T9 are **not explicitly covered by the v2 skill** — L04 is a generalization stress test. |

### Headline result — Gemma 4 26B (open-source, self-hosted via vLLM)

| Scenario | n | Baseline (no skill) | With v2 skill |
|---|:-:|:-:|:-:|
| **L01** sticky exclude | 10 | **0 / 10** — exclude silently drops after intervening turns | **10 / 10** ✓ — exclude survives all 10 runs, revoke works |
| **L02** referential decay | 10 | 10 / 10 | 10 / 10 *(baseline ceiling on this model)* |
| **L03** late contradiction | 10 | 10 / 10 | 10 / 10 *(baseline ceiling on this model)* |
| **L04** stacked + partial revoke + self-correct | 5 | 0 / 5 | 0 / 5 — **see per-turn breakdown below** |

### L01 — the clean isolation result

Same model, same scenarios, same scripted mocks. The ONLY variable
changed between columns is the skill body injected into the system
prompt. **Baseline: 0 / 10. With v2 skill: 10 / 10, zero failures,
zero errors across any turn of any run.** Single cleanest piece of
evidence this repo has. The Rule 4 mechanism (forced
`(바이오 제외 기준) …` restatement in every answer while a
persistent filter is active) keeps the filter top-of-attention
through the 5 intervening turns that defeat the baseline.

### L04 — where the skill helps, where it breaks

L04 is where the honest picture emerges. At the cell-pass level both
conditions fail 0 / 5 — the scenario is hard enough to defeat the skill
at the per-run aggregate. But the **per-turn** data tells the real story:

| L04 turn | What the turn tests | Baseline fails | With v2 skill fails | Interpretation |
|---|---|:-:|:-:|---|
| T6 | Ambiguous `"다시 전체"` with **3** stacked filters still in effect | 5 / 5 | 4 / 5 | marginal help; v2 stretches the B.1 rule from 1 filter to 3 |
| T7 | Partial revoke — `"2024년 조건만 풀어줘"` should drop ONE, keep TWO | 4 / 5 | **2 / 5** | clear help; rule 4 restatement cues the model to preserve the still-active filters |
| T9 | Self-correction — `"아 잠깐, 그냥 바이오도 같이 보여줘"` should revoke bio-exclude but preserve Major | 5 / 5 | 5 / 5 | **no help** — model interprets `같이` as "drop all filters" |
| T11 | Final full revoke — `"이제 Major 조건도 풀고 전체 다 보여줘"` | 0 / 5 | 0 / 5 | baseline already passes |

The T9 failure is honest and informative: when the user uses informal
expansion phrasing (`그냥 X도 같이`), the model over-generalizes and
drops the still-active Major filter. The v2 skill's revoke-classification
table (§B.1) covers explicit phrasings (`X 필터 해제`, `전체 초기화`)
but not this informal self-correction form. That's a clear v3 roadmap
item ([`FUTURE_PLAN.md`](FUTURE_PLAN.md)), not a hidden flaw.

### What this proves and does not prove

- **Proved**: on Gemma 4 26B with a production-like minimal system
  prompt, the v2 skill body reliably rescues long-horizon
  sticky-filter durability (L01) and measurably helps with
  3-filter state-keeping and explicit partial revoke (L04 T6 and T7).
- **Proved by omission**: the same benchmark that shows v2 winning on
  L01 shows v2 failing on L04 T9. The benchmark is not rigged to the
  skill's favor.
- **NOT yet proved**: cross-model generalization (only Gemma measured
  here; Qwen3.5 run aborted when we pivoted to L04). Also NOT yet
  proved: length-matched-generic-guidance is not the lever (the fair
  three-condition ablation from FUTURE_PLAN §1 is still pending).

### Historical note — Haiku 4.5 (v1 skill, n=3)

The first evidence of the skill affecting a frontier model was on
`claude-haiku-4-5` with the original skill body (v1), where L01
flipped 0 / 3 → 2 / 3. It's preserved in the results directory for
continuity; the Gemma 4 26B, v2 skill, n=10 numbers above supersede
it as the primary claim.

Full per-run JSON and markdown summaries (all matrix runs, both
models) are in
[`skills/korean-multiturn-rag/benchmarks/results/`](skills/korean-multiturn-rag/benchmarks/results/),
one subdirectory per run.

---

## Benchmark provenance and limitations

**The benchmark is self-authored.** Scenarios are hand-designed from
production failure modes; grading criteria are hand-written substring
assertions. This is inherently not an independent third-party
benchmark, and it is stated here rather than discovered by a reviewer.

**Why not run an existing benchmark instead?** We looked. RAGAS measures
RAG faithfulness but is not multi-turn. MT-Bench is multi-turn but not
Korean, not RAG, and doesn't measure filter persistence. BFCL covers
tool-use but is English. KLUE / HAE-RAE / KoBEST are single-turn Korean
NLP. No existing benchmark measures Korean multi-turn RAG state
persistence, Korean particle handling in tool params, or sticky-filter
durability across turns — which is precisely the gap the skill fills.
That's why we wrote our own.

**The fair-comparison critique we're aware of.** The current matrix
compares a *minimal* system prompt against a *minimal prompt plus the
full skill body*. A careful reader will rightly ask: is the improvement
because of *these specific Korean-multiturn patterns*, or because any
detailed prompt beats no detailed prompt? The current data cannot
distinguish those two hypotheses. A three-condition matrix (minimal /
length-matched-generic-guidance / actual-skill) would. That ablation is
on the roadmap ([`FUTURE_PLAN.md`](FUTURE_PLAN.md)) and will be treated
as required before any claim of "Korean-specific content is the lever."

**What the benchmark does reliably show:** for a given minimal
production-like system prompt, adding the skill body measurably
changes long-horizon behavior on a specific class of Korean multi-turn
failure modes we reproduce. That is a narrower, more defensible claim
than "the skill makes agents better."

---

## Quick start

### 1 · Read the field guide

Docs are side-by-side EN + KO — pick whichever reads faster for you.

| # | Topic | English | 한국어 |
|---|-------|---------|--------|
| 01 | Prompt-first debugging | [en](docs/en/01-prompt-first-debugging.md) | [ko](docs/ko/01-prompt-first-debugging.md) |
| 02 | Bug patterns in production agentic RAG | [en](docs/en/02-bug-patterns.md) | [ko](docs/ko/02-bug-patterns.md) |
| 03 | Session state design for multi-turn | [en](docs/en/03-session-state-design.md) | [ko](docs/ko/03-session-state-design.md) |
| 04 | Verifier cross-turn context | [en](docs/en/04-verifier-cross-turn.md) | [ko](docs/ko/04-verifier-cross-turn.md) |
| 05 | Korean NLP gotchas | [en](docs/en/05-korean-nlp-gotchas.md) | [ko](docs/ko/05-korean-nlp-gotchas.md) |
| 06 | Pharma-specific patterns | [en](docs/en/06-pharma-specific.md) | [ko](docs/ko/06-pharma-specific.md) |

### 2 · Install the skill (for Claude Code)

```bash
git clone https://github.com/papago2355/pharma-agent.git
cd pharma-agent
ln -s "$PWD/skills/korean-multiturn-rag" ~/.claude/skills/korean-multiturn-rag
```

Restart Claude Code. The skill's trigger keywords
(`X만` / `그럼 X는` / `더 보여줘` / `followup broadens` / `정보 없음`…)
auto-load it whenever they appear in your session.

**Codex / Copilot CLI**: same symlink pattern into that harness's
skill directory. **No harness?** Read
[`SKILL.md`](skills/korean-multiturn-rag/SKILL.md) as a checklist and
copy the patterns into your own system prompts.

### 3 · Run the benchmark

Two entry points. `pytest` for quick pass/fail across the full matrix;
`run_matrix.py` for per-cell pass rates written to a results directory
(the exact format the headline tables above were generated from).

**Against an open-source model via vLLM (reproduces the headline
Gemma 4 26B numbers above):**

```bash
cd skills/korean-multiturn-rag/benchmarks/behavioral
pip install -r requirements.txt

# vLLM server MUST be launched with tool-call flags:
#   --enable-auto-tool-choice --tool-call-parser <family>
# Supported parsers include: gemma4, qwen3_xml, hermes, llama3_json,
# mistral, pythonic, granite — see `vllm serve --help=all`.

BENCHMARK_BACKEND=openai_compat \
BENCHMARK_BASE_URL=http://localhost:8201/v1 \
BENCHMARK_API_KEY=EMPTY \
python run_matrix.py \
  --model google/gemma-4-26B-A4B-it --runs 10 \
  --scenarios l01 l02 l03 l04 --label gemma4-n10 \
  --concurrency 2
```

**Against Claude / Anthropic:**

```bash
export ANTHROPIC_API_KEY=...

pytest -v                                   # quick pass/fail
pytest -v -k "l01 or l02 or l03 or l04"     # just the long-horizon four

# per-cell pass-rate matrix:
python run_matrix.py --model claude-haiku-4-5 --runs 10 \
  --scenarios l01 l02 l03 l04 --label haiku-4-5-n10
```

**Using an older or experimental skill body** (default is the
promoted v2 at `SKILL.md`; override with an env var to read a
different file, e.g. the archived v1):

```bash
BENCHMARK_SKILL_FILE=SKILL-v1-legacy.md python run_matrix.py \
  --model google/gemma-4-26B-A4B-it --runs 5 \
  --scenarios l01 --label gemma4-v1-legacy
```

Results land under
[`benchmarks/results/<label>/`](skills/korean-multiturn-rag/benchmarks/results/)
with a `results.json` (per-cell detail, per-turn failures) and a
`summary.md` (markdown pass-rate table).

See [`benchmarks/behavioral/README.md`](skills/korean-multiturn-rag/benchmarks/behavioral/README.md)
for the full harness design.

---

## Who this is for

- Engineers **building** a Korean conversational RAG (customer
  support, legal research, pharma QMS, public-sector Q&A, insurance
  claims, any retrieval-grounded bot that speaks Korean).
- Teams whose bot works beautifully for the first 3 turns and
  silently degrades after that.
- Anyone debugging an agent whose **thinking log looks smarter than
  its final answer**.
- Regulated-industry engineers who need **auditable citations**, not
  just plausible ones.

Not for: toy chatbots, English-only deployments, free-chat assistants
without a retrieval backend.

---

## How this compares to memory libraries

Short version: **memory libraries solve a different layer.** Mem0, Zep,
and LangGraph checkpointers are *infrastructure* for persisting and
recalling conversation state — they give your agent somewhere to put
things. This repo is *prompt-level guidance* on what to put there and
how to reason over it when the user is typing Korean.

| Layer | Examples | What they answer |
|---|---|---|
| **Memory infrastructure** | Mem0, Zep, LangGraph checkpointers, custom session stores | "Where do I keep state between turns? How do I recall it?" |
| **Retrieval** | Milvus, Qdrant, pgvector, Weaviate, BGE-M3 hybrid | "Which chunks are relevant to this query?" |
| **This repo** | `korean-multiturn-rag` skill + field guide | "When a Korean user says `고형제만`, `그럼 X는`, `전체 다시`, or `바이오 제외` — what should the agent *do* with the state my memory layer already has?" |

These are composable, not competitive. You still need a memory store;
this skill tells the model how to use what's in it without dropping the
user's topic, re-retrieving unnecessarily, or silently losing a
persistent filter at turn 8. None of the memory libraries ship Korean
particle handling, hedge-phrase suppression, or the `전체 다시`
ambiguity rule — because those are prompt/behavior concerns, not
storage concerns.

If your multi-turn agent works fine in English and breaks in Korean
only after turn 5, the gap is almost certainly at this layer, not the
memory-infrastructure one.

---

## The non-obvious things this repo teaches

- **Why** a followup like "고형제만" returns *5,529 unrelated records
  instead of the 11 the user was looking at* — and the exact prompt
  rule that prevents it.
- **Why** your verifier flags correct multi-turn answers as
  hallucinations, and how a separate `prior_context` block with its
  own token budget fixes it.
- **Why** `if "만" in query` silently breaks on 만성, 만료, 만족,
  만약 — and what to replace it with.
- **Why** a persistent filter like "바이오 제외" silently drops at
  turn 8 when the user says "전체 다시" (the `전체` ambiguity bug),
  and the classification rule that survives 13 turns in production.
- **Why** an auditor-grade citation needs *three* fields, not one.
- **How to actually test a skill** — live tool-use loop with mock
  retrieval, not subagent recall theater.

Each claim comes with either a doc chapter explaining the mechanism,
a benchmark scenario demonstrating it, or both.

---

## Contributing

PRs welcome. The kind that help most:

- **New failure modes** paired with a reproducible scenario
  (short or long-horizon).
- **Additional models** in the benchmark matrix (Sonnet, Opus,
  Haiku 3.5, OpenAI-compatible endpoints for OSS models).
- **Translations** — the docs are EN + KO; if your team runs in JP,
  ZH, or VI, the patterns largely transfer and we'd love the coverage.
- **Anti-examples** — if you find a scenario where our skill makes
  things *worse*, that's a first-class contribution.

All examples in this repo use fictional mock names (`MOCK-SOP-NNN`,
`DEV-XX`, `팀-A/B/C`, `A정`, `B캡슐`, …). No proprietary or
company-specific identifiers. PRs that add real production data will
be rejected.

---

## License

MIT. Take whatever's useful.
