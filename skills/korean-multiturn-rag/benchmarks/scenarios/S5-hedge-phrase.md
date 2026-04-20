# S5 — Korean hedge-phrase regression

## Scenario (given to subagent)

A Korean RAG chatbot has a recurring complaint from users: the answer
often starts with "직접적인 내용은 없으나, …" or ends with "관련 정보를
찾을 수 없습니다" even when the references panel clearly shows documents
with high relevance scores (0.8+ on dense embedding similarity, some
with exact keyword hits in the document titles).

Example:
- Query: "정제의 경도 측정 허용 범위는?"
- References panel: 3 documents shown, top score 0.87, one with
  "[고형제] 시험타정방법서" in the title.
- Answer: "직접적인 내용은 없으나, 정제 관련 품질 기준은 <COMPANY>-SOP 시리즈에
  기술되어 있을 수 있습니다. 구체적인 수치는 별도 확인이 필요합니다."

The user is furious: "답이 있는데 왜 없다고 해?"

**Task:**

1. Diagnose the root cause. Is this a retrieval problem, an embedding
   problem, a prompt problem, or something else? Defend your answer.
2. Propose a concrete fix. If your fix is a prompt change, write out
   the actual replacement lines (in Korean is fine).
3. Name at least one OTHER Korean hedge phrase that should be
   suppressed in the same way.

## Rubric (hidden from subagent)

Passes if the answer satisfies **all** of:

- [ ] R1: Diagnoses this as a **prompt problem**, not a retrieval or
      embedding problem. Explicitly rules out retrieval (references
      are high-scoring and relevant).
- [ ] R2: Explains the mechanism: conservative "only cite what's in
      context" instructions cause the LLM to refuse on PARTIAL matches,
      when it should cite the partial info + name the gap.
- [ ] R3: Proposes prompt edits that **distinguish "no information"
      from "partial information"** and explicitly permit citing
      partial content with the gap called out.
- [ ] R4: Either forbids the literal phrase "직접적인 내용은 없으나"
      in the generation prompt, OR provides a positive instruction
      that would crowd it out ("우선 부분 정보를 인용하고 격차를 명시하라").
- [ ] R5: Names at least one other Korean hedge phrase (e.g.,
      "관련 정보를 찾을 수 없습니다", "확인이 필요합니다",
      "별도 확인 필요", "일반적으로", "…일 수 있습니다").
