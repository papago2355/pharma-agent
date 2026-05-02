# Multi-turn escape rules

Patterns 1–3 in `02-bug-patterns.md` cover what goes wrong on a *single*
followup turn: retrieval broadens, the verifier false-positives, the
tone hedges. This chapter is about what goes wrong over **several
consecutive turns** when the agent gets stuck and can't tell that it's
stuck — re-searching the same dead-end topic, paraphrasing a prior
answer back as a "new" answer, silently surfacing stale state from two
turns ago.

Stateless retrieval cannot escape these on its own. The agent needs:

1. **Signals** in session state that say "we already tried this and it
   didn't work" — durable across turns.
2. **Rules** in the system prompt that read those signals and *stop*
   the search loop instead of restarting it.
3. **A graceful exit** when the agent has correctly decided to stop —
   not a 14-character canned string.

This chapter covers all three. The patterns are agnostic to corpus
domain; they break in any conversational RAG that lets the agent
search again on every turn.

## The three failure modes the rules target

| Failure | What the user sees | What the agent is doing |
|---|---|---|
| **Hedge loop** | The same hedged "X에 대한 정보를 찾을 수 없습니다" three turns in a row | Re-running the same retrieval on the same topic. Each retry returns the same low-relevance set. |
| **Search decay** | Score graph drops 0.82 → 0.71 → 0.58 → 0.41 across turns. Final answer is generic. | Each turn the agent pivots to a slightly broader query, scores degrade, agent never escalates. |
| **Short-followup paraphrase** | User: "말한 거야" / "다시" / "맞나?" → agent re-renders the previous answer with synonyms | Agent treats the short follow-up as "elaborate on the last answer" instead of "differentiate, or escalate." |

Re-searching is the wrong move in all three. The right move is to
**escape**: tell the user honestly that we've already tried, surface
what we know, and ask for a different direction.

## Signal layer — the four session-state fields the rules read

These sit on top of the basic table in `03-session-state-design.md`.
They are **derived** signals, populated at the *end* of each turn,
not the start.

| Field | Type | When it's true |
|---|---|---|
| `last_answer_was_hedge` | `Optional[bool]` | The previous answer was an honest no-info / out-of-scope response. `None` = unknown (verifier didn't run); never default to `False`. |
| `last_strategy` | `str` | Which planner strategy was selected (e.g. `direct_lookup`, `subset_filter`, `analytical`). Used by the differentiation rule. |
| `search_history` | `List[Dict]`, cap 3 | One entry per recent turn: `{top_score, ref_count, strategy}`. Lets a rule see "the last two turns retrieved low-relevance results." |
| `last_answer_summary` | `str`, ≤ 200 chars | Pure head-truncation of the previous answer. **Not a regex extract of a "verdict line."** Used by the short-followup rule to detect paraphrase. |

`last_answer_was_hedge` is the most failed-at-design field of the four.
The temptation is to compute it with a regex over the answer text
(`"확인되지 않[음습]"`, `"범위 밖"`, …). Don't. The agent rephrases its
own hedges constantly, the regex misses, and the session state ends
up *confidently wrong* — which is worse than `None`. Source the signal
from a verifier schema field (next section).

## Verifier dual-signal: `is_hedge` vs `is_dead_end_escape`

Chapter 04 covers the verifier as a single boolean (`pass`).
Production multi-turn needs **two more independent fields**, both
judged by the verifier:

```json
{
  "pass": true,
  "is_hedge": true,
  "is_dead_end_escape": false,
  "severity": "low",
  "reason": "..."
}
```

- `is_hedge`: was this answer an honest no-info? **Independent of
  `pass`** — an honest no-info is still a *passing* answer; it just
  needs to propagate into next-turn state.
- `is_dead_end_escape`: was this answer the agent *escalating* because
  we've already searched and failed? **Independent of `is_hedge`** —
  a dead-end escape is "I tried, here's what I tried, give me a
  different angle." A hedge is "I don't know."

Different next-turn rules trigger off each:

- `is_hedge` → drives the **hedge-loop escape** rule (don't re-search
  the same topic).
- `is_dead_end_escape` → is the regression-test target (replay tests
  assert that the agent actually reached an honest dead-end, not just
  hedged).

Why split them: a verifier prompt that conflates them produces a
single `is_no_info: bool` that fires `true` for both legitimate hedges
and dead-end escapes — and the agent then can't tell apart "I should
escape now" from "I just hedged." The split costs one extra schema
field; the clarity it buys downstream is significant.

## The three rules

Each rule reads exactly the signals defined above. Each is **two
sentences in the system prompt** plus one line in the followup
template — no more.

### Rule A — Hedge-loop escape

```text
HEDGE-LOOP ESCAPE: if last_answer_was_hedge is true AND the current
turn is asking about the same topic as last_answer_summary, do NOT
re-search. Call final_answer with a thought that names the dead-end
honestly and suggests an alternative direction. Phrase the dead-end
in your own words — do not copy a fixed string.
```

Triggered by: `last_answer_was_hedge=true` + an inline topic-similarity
judgment by the LLM.

### Rule B — Search-decay escape

```text
SEARCH-DECAY ESCAPE: if at least 2 of the last 3 entries in
search_history have top_score < 0.6 AND ref_count <= 2, do NOT issue
another search on a paraphrase of the same topic. Escalate via
final_answer.
```

Triggered by: aggregation over the cap-3 `search_history` buffer.
Numeric, not semantic — these are *scoreboard* facts the agent can
read directly.

### Rule C — Short-followup differentiation

```text
SHORT-FOLLOWUP DIFFERENTIATION: if the user's turn is < 30 chars AND
last_answer_summary is non-empty, your answer MUST differentiate from
last_answer_summary. Do not paraphrase, do not re-render. If you have
no new information, escape via Rule A.
```

Triggered by: simple length + presence check, then a behavioral
instruction. The `< 30 chars` cutoff matches the empirical failure
mode ("말한 거야" — 5 chars; "다시 보여줘" — 7 chars).

**Known refinement**: `< 30` over-fires on benign acknowledgments
("확인했어요", "다음 질문"). Two ways to harden:

- Tighten the threshold to `< 20 chars` *and* pair it with an explicit
  intent check ("user is asking the same thing again"). Stricter rule,
  fewer false positives.
- Keep `< 30` but only fire when `active_topic` matches between the
  last two turns. Avoids the rule firing on conversational chitter.

Pick the variant that matches your data. Both are honest; the first
is slightly conservative, the second is slightly liberal.

## State hygiene: clear sticky keys on 0-result turns

When a turn returns 0 results, **clear** the sticky session keys
(`last_records`, `last_distributions`, whatever your schema names
them). Do not "leave them as-is from the prior turn."

The bug this prevents:

```
Turn 1: search → 11 records → set last_records = [11 rows]
Turn 2: search → 0 results → ??? leave last_records as-is?
Turn 3: user asks "그 중 X만" → agent filters last_records from TURN 1
        as if those were "what we just retrieved" → wrong answer
```

The verifier won't catch this — turn 1's rows ARE valid prior context
*at turn 2*, but they are stale by *turn 3*. The agent has no way to
tell the difference unless the state is explicitly cleared.

```python
if result.records:
    session.last_records = result.records
else:
    session.last_records = None   # or .pop / del
```

The `else` branch is the entire fix. It's never the hard part; the
hard part is remembering to write it.

## Per-instance dedup, not list-level dedup

If your tool layer hashes the full param set to deduplicate calls,
this trick defeats it:

```
call 1: document_fetch(files=[A])         # hash(A)         → new
call 2: document_fetch(files=[A, B])      # hash(A,B)       → new
call 3: document_fetch(files=[A, B, C])   # hash(A,B,C)     → new
```

Each call is "distinct" by full-param hash, so file `A` is fetched
three times. The agent didn't even need to be malicious — it added
genuinely-new files each turn and the dedup quietly let `A` through
each time.

Fix: dedupe per-instance, not per-call. Track a `Set[str]` of files
already fetched in this loop, and at execution time filter the
params down to only the files not in the set:

```python
fetched_files: Set[str] = set()

for action in plan:
    if action.name == "document_fetch":
        new_files = [f for f in action.params["files"]
                     if f not in fetched_files]
        if not new_files:
            continue   # skip the call entirely
        action.params["files"] = new_files
        fetched_files.update(new_files)
    execute(action)
```

This generalizes to any batch tool (`document_fetch`, `bulk_lookup`,
multi-id `record_get`, …). The list-level dedup pattern is seductive
because the obvious test case passes — `[A]` followed by `[A]` is
correctly skipped. The `[A]` → `[A,B]` → `[A,B,C]` path needs its own
test, and most teams don't write it.

## Graceful exit: LLM-composed, not canned

The default no-results path most teams ship looks like this:

```python
if not result.has_data():
    return "검색 결과를 찾지 못했습니다. 다른 키워드로 시도해 주세요."
```

This is **honest** but **useless**. Three of four regression failures
in our production data sat on this path: the agent had searched, found
nothing, but the user's earlier turns held perfectly good alternatives
the canned string couldn't surface.

Replace it with an LLM call constrained to **one of two output
shapes**:

- **(A) Honest no-match + alternatives anchored in session state.**
  Pull candidates from `shown_documents` + the last 3 search summaries
  + wiki, if any. *"정확한 X는 찾지 못했지만, 이전에 본 Doc-A / Doc-B
  가 관련될 수 있습니다. 어느 쪽을 보시겠어요?"*
- **(B) Honest no-match + a focused clarifying question with concrete
  options.** *"X를 찾지 못했습니다. Y(영역) 또는 Z(영역)를
  의미하셨나요?"*

Inputs to the handler:

```python
compose_graceful_no_results(
    query=original_query,
    shown_documents=session.shown_documents,
    recent_searches=session.search_history,   # cap 3
    agent_thoughts=last_react_thoughts,       # optional, helps a lot
)
```

Fail-soft: if the LLM call fails or returns empty, fall back to a
brief polite system message — never silently render `""`. The fallback
should still be short ("다시 한 번 명확히 말씀해 주세요.") but it's
the backup, not the primary path.

This is the highest-leverage change of the whole chapter. It cost
three regression-failure repros to land it; everyone else can copy
the pattern in an afternoon.

## Anti-pattern: prescribed-phrase verbatim emission

A neighbor of the canned-string trap. The temptation:

```yaml
# system prompt rule (DO NOT SHIP THIS)
On dead-end escapes, the final answer MUST start with the literal
string "이미 검색했으나" so the harness can deterministically detect
dead-end escapes.
```

This couples the prompt to the harness. Two failure modes follow:

1. The LLM paraphrases ("이전에 검색해 보았으나…" / "이미 확인한
   결과…"). The harness regex misses. The harness flags a real escape
   as a non-escape.
2. The prompt rule constrains the agent's expression to a fixed
   phrasing — which is *exactly* what the "let the LLM route"
   principle warns against, just on the answer-side instead of the
   query-side.

Fix: drop the verbatim-string requirement from the prompt. Have the
**verifier** judge whether an answer is a dead-end escape
(`is_dead_end_escape: bool`), and have the harness read the verifier
signal — not the answer substring.

The same lesson generalizes to any "the prompt instructs the agent to
emit a specific Korean string so my downstream system can detect it"
pattern. If you find one, replace it with a structured signal at a
boundary the LLM doesn't have to reproduce verbatim.

## Putting it together — checklist

- [ ] Verifier emits `is_hedge: bool` and `is_dead_end_escape: bool`
      as schema fields, **independent of `pass`**.
- [ ] Session state has `last_answer_was_hedge` (Optional, sourced
      from the verifier — *never* a regex), `last_strategy`,
      `search_history` (cap 3), `last_answer_summary` (head 200
      chars).
- [ ] Three escape rules in the system prompt, reading the four
      signals above.
- [ ] 0-result turns explicitly clear sticky session keys.
- [ ] Batch-tool dedup is **per-instance** (set membership), not
      **per-call** (param hash).
- [ ] The no-results path calls an LLM-composed graceful handler with
      session-state inputs, plus a polite fail-soft fallback.
- [ ] No prompt rule asks the agent to emit a verbatim Korean string
      for downstream detection. All cross-system signals are
      structured verifier fields.

If the agent stops searching when it should, surfaces what it does
know, and asks for a different angle when it has nothing — the rest
of the multi-turn UX builds on top of that. Without these, every
other multi-turn pattern is a patch below the waterline.
