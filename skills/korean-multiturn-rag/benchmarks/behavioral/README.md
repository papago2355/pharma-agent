# Behavioral benchmark — Korean multi-turn RAG

Real behavioral test, not skill-recall. Each scenario runs a **full
multi-turn conversation** against an Anthropic model with scripted mock
tools, then grades the agent's actual tool calls and final text against
the rubric for each turn.

## What this measures vs. the sibling design-review suite

| | `benchmarks/scenarios/` (design review) | `benchmarks/behavioral/` (this) |
|---|---|---|
| Subject under test | Subagent answering a design question | Live agent holding a Korean multi-turn conversation |
| Signal | Recall of skill bullets | Tool-call pattern + state behavior |
| False-positive risk | High (tautological rubric) | Low (behavior is observable) |
| Cost | Cheap, one LLM call per scenario | One full loop per scenario × N runs × 2 configs |
| Catches over-firing? | No | Yes (adversarial scenarios) |

Use both. Design-review is the smoke test. Behavioral is the real eval.

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
```

## Run

```bash
# full matrix: all scenarios × {no_skill, with_skill} × N runs
pytest benchmarks/behavioral/ -v

# one scenario
pytest benchmarks/behavioral/ -v -k s01

# quick: 1 run per cell
BENCHMARK_RUNS=1 BENCHMARK_PASS_THRESHOLD=1 pytest benchmarks/behavioral/ -v

# model matrix
BENCHMARK_MODEL=claude-haiku-4-5 pytest benchmarks/behavioral/ -v
BENCHMARK_MODEL=claude-opus-4-7   pytest benchmarks/behavioral/ -v
```

## Scenario coverage

Intentionally **pharma-generic** (not tied to any specific company) plus
cross-domain to prove the skill doesn't only work on QMS corpora.

| File | Category | What it tests |
|------|----------|---------------|
| `s01_pharma_subset_filter.yaml` | Positive | Turn 2 "고형제만" must filter prior rows, NOT re-call the tool. |
| `s02_pharma_adversarial_particle.yaml` | Adversarial | "만성질환" (stem contains 만) MUST trigger new retrieval, not subset-filter. |
| `s03_support_subset_no_particle.yaml` | Cross-domain + phrasing | E-commerce orders, subset phrased with "중에서 / 위주로" — no literal 만 — must still filter in place. |

## Extending

Add a `scenarios/sNN_*.yaml` file following the schema:

```yaml
name: ...
domain: ...
system_prompt: |
  (base agent system prompt, skill-free)
tools:
  - name: ...
    description: ...
    input_schema: {...}
mock:
  - tool: <name>
    when: {query: "substring"}       # params match loosely
    returns: {...}                   # tool_result payload (dict → JSON)
turns:
  - user: "..."
    expect:
      tool_called: <name>|null       # null = agent must not call anything
      tool_params_contain: {...}
      tool_params_absent: [...]      # forbidden substrings in any param
      answer_contains: [...]
      answer_not_contains: [...]
```

The runner is domain-agnostic — the scenario carries its own system
prompt, tool schema, and mock data.

## What to add next (left as TODO)

- **Sticky-exclude over 3+ turns**: user says "바이오 제외" on turn 2;
  turn 4 unrelated subset must still carry that exclusion.
- **Referential stability**: "2번째 문서 자세히" on turn 3 vs turn 5
  must resolve to the same doc after a subset filter.
- **Hedge-phrase regression**: high-score mock retrieval + base prompt
  without the literal hedge ban → expect answer to cite content, not
  lead with "직접적인 내용은 없으나".
- **Legal-domain cross-check**: precedent search in Korean, same
  invariants as pharma.
- **Router false-fire**: fresh queries containing 그럼 ("그럼에도…").

Each item above follows the same YAML shape. Adding one is ~30 minutes
including thinking through the correct mock behavior.

## Result artifact

A future extension can emit `results/report-YYYY-MM-DD.md` aggregating
per-scenario, per-config pass rates. For now, pytest's `-v` output is
the source of truth and can be piped into a markdown table by hand.
