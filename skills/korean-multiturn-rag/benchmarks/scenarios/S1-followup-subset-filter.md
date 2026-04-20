# S1 — Followup subset-filter behavior

## Scenario (given to subagent)

You are designing a multi-turn Korean chatbot backed by a retrieval tool
`qms_search(query, title_contains[], table_filter, grade, team, state,
date_from, date_to)` over a structured database of ~100,000 deviation
records.

Turn 1
- User: "최근 원료 이물 관련 일탈 보여줘"
- You called `qms_search(query="원료 이물", table_filter="일탈",
  date_from="2025-01-01")` and got **11 records back**. You displayed
  them to the user.

Turn 2
- User: "고형제만 추려줘"

**Task:** describe exactly what the agent should do on turn 2. Include:
- The tool call(s) you make (with parameters), OR explicit "no tool call".
- The reasoning for that choice.
- What session-state or prior-context data you rely on.
- What would go wrong if you chose a different approach.

Be specific. One short paragraph per point.

## Rubric (hidden from subagent)

Passes if the answer satisfies **all** of:

- [ ] R1: Does NOT call `qms_search` again on turn 2.
- [ ] R2: Filters the 11 rows from turn 1 in-place (in the thought/answer).
- [ ] R3: Explains that re-searching would lose the "원료 이물" topic
      filter and return generic unrelated records (broadening failure).
- [ ] R4: References prior-turn raw records / session state as the
      source of truth for the filter.
- [ ] R5: Does NOT propose only keyword-matching "고형제" in a literal
      title search as the primary approach (because 고형제 is a category
      label, not a product-title token).
