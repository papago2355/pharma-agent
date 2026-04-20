# S4 — Post-generation verifier for multi-turn answers

## Scenario (given to subagent)

A Korean multi-turn RAG chatbot runs a post-generation verifier that
inspects the final answer against the evidence the generation LLM saw.
The verifier returns `{pass: bool, issues: [str], severity: str}`. When
`pass=false`, the UI prepends a warning banner to the answer.

Current bug: the verifier **false-positives** on legitimate followups.

Reproduction:

- Turn 1: user asks for "원료 이물 일탈 목록". Agent retrieves 11 records
  and shows them with a total count ("총 11건").
- Turn 2: user says "고형제만 추려줘". Agent filters the 11 prior records
  in-place (no new retrieval needed — the 11 rows are in session state)
  and responds: "11건 중 고형제는 4건입니다. PR-XXX, PR-YYY, ..."
- Verifier fires. It receives only turn 2's generation context (empty,
  since no new retrieval ran). It cannot find "11건" anywhere in that
  context. It returns `pass=false, issues=["총 11건이라는 주장은 근거 없음"]`.
- UI shows WARN banner. User loses trust in a correct answer.

**Task:** redesign the verifier. Specifically:

1. What inputs does it receive?
2. What are the rules for what to flag vs not flag?
3. What severity levels exist and what happens at each?
4. When (if ever) should verification be skipped entirely?

## Rubric (hidden from subagent)

Passes if the answer satisfies **all** of:

- [ ] R1: Verifier receives a **separately labeled** `prior_context` /
      prior-turn block as one of its inputs, alongside this-turn
      generation context.
- [ ] R2: Rules **explicitly whitelist** claims that trace to prior
      context (counts, distributions, record fields reused from
      prior turns).
- [ ] R3: Prior context is passed as raw structured rows / distributions,
      not as a prose summary.
- [ ] R4: Prior context has its own character/token budget, independent
      of the main generation context budget (so long retrievals can't
      starve the prior block).
- [ ] R5: At least two severity levels (e.g., high/low), with behavior
      that never HARD-BLOCKS the answer on low severity.
- [ ] R6: Names at least one case where verification is skipped (turn
      1 with high-score retrieval, short answers, refusals, or casual
      chat — any one is fine).
