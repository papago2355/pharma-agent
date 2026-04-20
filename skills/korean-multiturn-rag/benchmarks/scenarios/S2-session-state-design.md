# S2 — Session-state design for Korean multi-turn RAG

## Scenario (given to subagent)

You are designing session state for a Korean-language multi-turn RAG
chatbot. Users ask questions over multiple turns. They expect followups
like "그럼 X만", "더 보여줘", "2번째 문서 자세히", "방금 거 요약" to work
correctly without them having to repeat context.

The retrieval backend is a hybrid search (dense + sparse) over ~50k
documents, plus a structured table with ~100k records. Each search
returns documents and records with metadata (IDs, department, date,
title, scores).

**Task:** design the session-state schema. Answer:

1. What fields do you persist between turns? For each field, give:
   - The field name and data type.
   - Why it exists (what followup pattern it enables).
2. What do you explicitly **NOT** persist, and why?
3. When surfacing prior-turn state into the next turn's prompt, what
   format do you use, and why?

Be concrete. A numbered list is fine.

## Rubric (hidden from subagent)

Passes if the answer satisfies **all** of:

- [ ] R1: Persists raw structured records/rows from the last search
      (not just a summary).
- [ ] R2: Persists pre-computed distributions / aggregate counts for
      analytical followups ("가장 빈번한 X", "통계").
- [ ] R3: Persists something equivalent to `active_topic` or
      `last_query` to prevent topic drift.
- [ ] R4: Persists a persistent-exclude / cross-turn-exclude mechanism
      ("바이오 제외" stays sticky until revoked).
- [ ] R5: Explicitly argues AGAINST persisting only conversation
      history / text summaries, with the reason that the next turn
      needs rows it can filter.
- [ ] R6: Specifies the handoff format is an **actionable structured
      block** (labeled, rows visible) — not ambient prose like
      "Previously shown 10 records."
