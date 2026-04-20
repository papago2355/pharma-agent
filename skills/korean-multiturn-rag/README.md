# korean-multiturn-rag

Short field-guide snippets for engineers building a **Korean multi-turn
chatbot** — session state design, subset-filter followups, particle
stripping, verifier cross-turn context, hedge-phrase regression,
LLM-over-regex routing, persistent-filter disambiguation.

**This is reference material for the builder, not an inference-time
magic wand.** See [`benchmarks/`](benchmarks/) for exactly what the skill
does and doesn't measurably change on real models.

## Install

### For Claude Code

```bash
# from the pharma-agent repo root
ln -s "$PWD/skills/korean-multiturn-rag" ~/.claude/skills/korean-multiturn-rag
```

Restart your Claude Code session. The skill's `description` triggers on
Korean multi-turn patterns like "X만", "그럼 X는", "더 보여줘", "followup
broadens instead of filtering", "verifier flags correct multi-turn
answer", etc. When Claude Code sees any of those, it auto-loads the
skill body.

### For Codex CLI, Copilot CLI, or any skill-aware harness

Same symlink pattern into that harness's skill directory. Check your
harness's docs for the path (e.g., Codex uses `~/.agents/skills/`).

### No harness?

Just read [`SKILL.md`](SKILL.md) as a markdown field-guide checklist.
Apply the patterns by hand into your own agent's system prompts,
verifier prompts, and routing code. Every pattern is stack-agnostic —
`SKILL.md` doesn't assume any framework.

### Verify install

```bash
ls -la ~/.claude/skills/korean-multiturn-rag/SKILL.md
# Should show the symlink target
```

Then in a new Claude Code session, ask something Korean-multi-turn-ish
("how do I handle '고형제만' as a followup filter?") — the skill should
load automatically. In the response panel you'll see
`[Loading skill: korean-multiturn-rag]` or similar harness log line.

## Run the benchmarks

The skill ships with a TDD benchmark suite that runs the same scenarios
**without** and **with** the skill injected, so you can see for yourself
what it actually changes.

```bash
cd benchmarks/behavioral
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

# run the full matrix (11 short scenarios + 3 long-horizon, both conditions)
pytest -v

# just the long-horizon (12+ turn) scenarios
pytest -v -k "l01 or l02 or l03"

# a different model
BENCHMARK_MODEL=claude-sonnet-4-6 pytest -v
```

Current honest result on Haiku 4.5: **most scenarios pass in both
conditions (skill has no measurable effect).** A single long-horizon
scenario (L01 — sticky exclude over 13 turns) fails in both conditions
and is the active target for skill improvement. See
[`benchmarks/results/behavioral/`](benchmarks/results/behavioral/) for
the full breakdown.

## Uninstall

```bash
rm ~/.claude/skills/korean-multiturn-rag
```

The symlink removes; the repo stays intact.

## Contents

```
korean-multiturn-rag/
├── SKILL.md                         # the skill body — read this first
├── README.md                        # this file
├── benchmarks/
│   ├── README.md                    # benchmark suite overview
│   ├── scenarios/                   # design-review scenarios (S1–S6)
│   ├── behavioral/                  # live tool-use pytest suite
│   │   ├── runner.py                # Anthropic API multi-turn driver
│   │   ├── mocks.py                 # declarative mock tool handler
│   │   ├── grading.py               # rubric assertions
│   │   ├── test_behavioral.py       # pytest entry point
│   │   └── scenarios/               # YAML scenarios (s01–s11, l01–l03)
│   └── results/                     # captured RED/GREEN grading notes
```

## What the skill covers

- **A. Subset followup → filter-in-thought, not re-retrieve** — avoid the
  "X만" broadening failure.
- **B. Session state: rows + distributions + sticky excludes** — what
  to persist between turns (not just conversation history).
- **B.1. Persistent-filter disambiguation** — classify Korean "reset-
  looking" words (전체, 모두, 다시, 새로) as AMBIGUOUS and keep the
  active filter unless the user EXPLICITLY revokes.
- **C. Particle stripping before exact-substring filters** —
  "고형제만" → `["고형제"]`, never `["고형제만"]`.
- **D. Verifier: prior context as a separate block with its own budget**
  — why post-gen verifiers false-positive on legitimate cross-turn
  reasoning and how to fix it.
- **E. Hedge-phrase regression** — "직접적인 내용은 없으나…" is a
  prompt problem, not a retrieval problem.
- **F. LLM routing, not regex** — `if "만" in query` breaks on 만성,
  만료, 만족, 만약, etc.

See [`SKILL.md`](SKILL.md) for the full text and rationalization table.
