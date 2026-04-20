# pharma-agent

> **A field guide + testable skill for building Korean multi-turn RAG
> chatbots.**
> Patterns from real production that don't show up in toy demos —
> each pattern paired with a runnable behavioral benchmark so you can
> see for yourself what moves and what doesn't.

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Skill: korean-multiturn-rag](https://img.shields.io/badge/skill-korean--multiturn--rag-7c3aed)](skills/korean-multiturn-rag/)
[![Benchmark: Haiku 4.5](https://img.shields.io/badge/benchmark-Haiku%204.5-orange)](skills/korean-multiturn-rag/benchmarks/results/behavioral/)
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
   Anthropic API + scripted mock tools + pytest grading on actual
   tool calls and final text, including **13-turn long-horizon
   scenarios** that surface failures two-turn tests can't.

---

## Proof that it does something

The first behavioral scenario where our skill flipped a baseline
failure into a pass on a frontier model:

| Scenario | Baseline (no skill) | With skill | Model |
|---|:-:|:-:|---|
| **L01 — sticky exclude over 13 turns**  (`바이오 제외` set early, user later says "전체 다시 보여줘") | **0 / 3 FAIL** — exclude silently drops | **2 / 3 PASS** — exclude survives; only drops on explicit revoke | `claude-haiku-4-5` |

Full breakdown — what works, what doesn't, which scenarios the
baseline already handles natively, which the skill still can't fix —
in
[`skills/korean-multiturn-rag/benchmarks/results/behavioral/`](skills/korean-multiturn-rag/benchmarks/results/behavioral/).

**Honest caveat we won't hide:** on the short (2–3 turn) suite and on
two of three long-horizon scenarios, the skill's delta is zero —
Haiku 4.5 already handles those patterns. The value is concentrated
in long-horizon state management (see L01) and likely much larger on
smaller models (cross-model testing is a planned next step).

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

```bash
cd skills/korean-multiturn-rag/benchmarks/behavioral
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
pytest -v                                 # full matrix, both conditions
pytest -v -k "l01 or l02 or l03"          # just long-horizon
BENCHMARK_MODEL=claude-sonnet-4-6 pytest  # different model
```

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
