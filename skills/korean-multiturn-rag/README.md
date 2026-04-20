# korean-multiturn-rag

Short field-guide snippets for engineers building a **Korean multi-turn
chatbot** — session state design, subset-filter followups, particle
stripping, verifier cross-turn context, hedge-phrase regression,
LLM-over-regex routing, persistent-filter disambiguation.

> **This is reference material for the builder, not an inference-time
> magic wand.** See [`benchmarks/results/behavioral/`](benchmarks/results/behavioral/)
> for exactly what the skill does and doesn't measurably change on
> real models.

For install instructions, see the [repo root README](../../README.md#2--install-the-skill-for-claude-code).

## What the skill covers

| § | Pattern | What it teaches |
|---|---------|-----------------|
| A | Subset followup → filter-in-thought, not re-retrieve | Avoid the "X만" broadening failure (5,529 irrelevant rows instead of the 11 the user was looking at). |
| B | Session state: rows + distributions + sticky excludes | What to persist between turns — not just conversation history. |
| B.1 | Persistent-filter disambiguation | Classify Korean "reset-looking" words (`전체`, `모두`, `다시`, `새로`) as AMBIGUOUS; keep the active filter unless the user EXPLICITLY revokes. |
| C | Particle stripping before exact-substring filters | `"고형제만"` → `["고형제"]`, never `["고형제만"]`. |
| D | Verifier: prior context as a separate block with its own budget | Why post-gen verifiers false-positive on legitimate cross-turn reasoning and how to fix it. |
| E | Hedge-phrase regression | `"직접적인 내용은 없으나…"` is a prompt problem, not a retrieval problem. |
| F | LLM routing, not regex | `if "만" in query` breaks on 만성, 만료, 만족, 만약, etc. |

Read [`SKILL.md`](SKILL.md) for the full text, worked examples, and
rationalization table.

## Run the benchmarks

The skill ships with a TDD benchmark suite that runs the same scenarios
**without** and **with** the skill injected, so you can see for yourself
what it actually changes.

```bash
cd benchmarks/behavioral
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

# full matrix (11 short scenarios + 3 long-horizon, both conditions)
pytest -v

# just the long-horizon (12+ turn) scenarios
pytest -v -k "l01 or l02 or l03"

# a different model
BENCHMARK_MODEL=claude-sonnet-4-6 pytest -v
```

Current honest result on Haiku 4.5: on short (2–3 turn) scenarios
the skill has **no measurable effect** — the model already handles
those patterns. The one long-horizon scenario where the skill flipped
a real failure (L01 sticky-exclude durability over 13 turns: 0/3 →
2/3) is documented in
[`benchmarks/results/behavioral/haiku-4-5-l01-sticky-exclude.md`](benchmarks/results/behavioral/haiku-4-5-l01-sticky-exclude.md).

See the full breakdown in
[`benchmarks/results/behavioral/`](benchmarks/results/behavioral/).

## Layout

```
korean-multiturn-rag/
├── SKILL.md                         # the skill body — read this first
├── README.md                        # this file
└── benchmarks/
    ├── README.md                    # benchmark suite overview
    ├── scenarios/                   # design-review scenarios (S1–S6)
    ├── behavioral/                  # live tool-use pytest suite
    │   ├── runner.py                # Anthropic API multi-turn driver
    │   ├── mocks.py                 # declarative mock tool handler
    │   ├── grading.py               # rubric assertions
    │   ├── test_behavioral.py       # pytest entry point
    │   └── scenarios/               # YAML scenarios (s01–s11, l01–l03)
    └── results/                     # captured RED/GREEN grading notes
```
