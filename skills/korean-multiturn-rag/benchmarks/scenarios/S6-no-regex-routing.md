# S6 — Korean intent routing without regex

## Scenario (given to subagent)

A Korean multi-turn RAG chatbot needs to route each user turn to one of
three behaviors:

1. `new_search` — fresh retrieval with the user's query.
2. `subset_filter` — filter the prior-turn records without re-searching
   (triggered by followups like "고형제만", "Major 등급만", "그럼 X는",
   "2번째 거만 자세히").
3. `analytical_followup` — reuse prior-turn aggregate counts without
   re-searching (triggered by "가장 빈번한", "제품별 건수", "순서대로").

A junior engineer proposes this router:

```python
def route(query: str, has_prior: bool) -> str:
    if not has_prior:
        return "new_search"
    if "만" in query or "그럼" in query:
        return "subset_filter"
    if "가장" in query or "제품별" in query or "순서" in query:
        return "analytical_followup"
    return "new_search"
```

**Task:**

1. List every specific way this router will silently break on real
   Korean input. Give at least three concrete failing query examples
   and explain why each fails.
2. Propose a replacement design. Be explicit about which component
   makes the routing decision and what evidence it uses.
3. State one guarantee the replacement provides that the regex router
   cannot.

## Rubric (hidden from subagent)

Passes if the answer satisfies **all** of:

- [ ] R1: Identifies at least two distinct Korean-specific failure
      modes of `"만" in query` (examples: "고만해" / "얼만큼" / "만약"
      / noun "만" meaning "bay" / matched inside unrelated words).
- [ ] R2: Identifies that `"만" in query` will trigger incorrectly on
      a fresh non-followup query that happens to contain 만
      morphologically.
- [ ] R3: Identifies that legitimate subset-filter queries without the
      literal particle 만 ("고형제로 좁혀줘", "Major 등급 위주로",
      "종결된 것만 빼고") will route to `new_search` incorrectly.
- [ ] R4: Proposes **LLM-level routing** (have an LLM call decide
      the action, or expose it as a tool parameter the LLM fills) —
      NOT a larger regex / keyword list / rule table.
- [ ] R5: States an explicit guarantee, e.g., "routing decisions survive
      an LLM swap" / "new followup phrasings require no code change" /
      "routing failures are visible in a single decision log entry,
      not scattered across branch coverage."
