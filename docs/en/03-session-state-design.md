# Session state for multi-turn agentic RAG

Single-turn RAG is stateless. Multi-turn breaks the moment you try to
retrofit "remember the last thing" on top of a stateless pipeline. Design
state from the beginning.

## What to persist between turns

Most teams persist conversation history (user + assistant messages) and
call it done. That's insufficient. At minimum, persist:

| Field | Why |
|-------|-----|
| `shown_documents` | Which references the user actually saw. Prevents "show me more" from re-recommending the same docs. |
| `last_shown_documents` | Ordered refs from the immediate prior turn. Lets "2번째 문서" resolve by position. |
| `last_filters` | Which dept/doc/date filters the prior turn applied. Followups often want to refine these. |
| `last_records` | Top-N raw structured rows from the last search. Enables subset-filter followups without re-searching. |
| `last_distributions` | Pre-computed aggregate counts (by state, team, product). Lets analytical followups answer without re-searching. |
| `active_topic` | A short human-readable label for the current conversation focus. Prevents topic drift. |
| `persistent_exclude` | Cross-turn exclusions ("바이오 제외"). Must persist until the user explicitly revokes. |
| `disambiguation` | Term → chosen meaning. Sticky for the session. |

## The key insight: persist raw rows, not just summaries

If the user says "고형제만 추려줘" on turn 2, the agent needs the actual
rows from turn 1 to filter. If you only persisted a text summary, the
agent has to re-search — and re-searching loses the prior filter context.

The cost of persisting 20 structured rows per turn is trivial compared
to the cost of a broadened re-search.

## The handoff format matters

Persisting records is step 1. Step 2 is surfacing them to the next turn's
agent in a way that's **actionable**, not just ambient context.

Bad:
```
Previously shown 10 records.
```

Good:
```
[PRIOR RECORDS — FILTERABLE]
Source query: 원료 이물 일탈
Records: 10

  [1] PR-xxxxx | Major | xxxx팀 | 종결 | 2025-03-31
      xxxx xx/xxxmg xxxxxx 원료 이물 발견 건
  [2] PR-xxxxx | Major | xxx팀 | 종결 | 2025-02-14
      xxxxx정 xmg xxxxx 2차 xxxx액 제조 중 ...
  ...
```

The difference: the second form tells the agent "these are rows, you can
filter them." The first form is text the LLM has to re-parse.

## Session TTL and cleanup

- 24-hour TTL is reasonable for most chat UX.
- Cleanup every 30 minutes. Don't do it on every request.
- Survive container restarts: write to SQLite + keep a hot in-memory cache.
- Watch for unbounded growth: cap `shown_documents` to last 10, `topic_history`
  to last 5, `rejected_documents` to last 5.

## What *not* to persist

- Full tool outputs — too large, mostly redundant.
- LLM raw outputs — re-derivable and can leak reasoning you don't want reused.
- User-provided sensitive values that weren't explicitly opted into storage.

## Followup detection

"Is this turn a followup?" is harder than it looks. Don't use "was there a
prior assistant message?" — that's true for every turn after the first.
Better signals:

- Topic similarity to the prior turn (embedding similarity on rewritten queries).
- Explicit references ("이중", "아까", "방금", "위에서").
- Subset-filter keywords ("만", "X만", "그럼 X는").

Bias toward "yes, this is a followup" when in doubt — the cost of surfacing
prior context incorrectly is low (agent can ignore), while the cost of
missing a followup is high (agent re-searches broadly, loses context).
