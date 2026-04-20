# S3 — Korean particle handling in filter parameters

## Scenario (given to subagent)

You are implementing the agent layer of a Korean-language RAG system.
The retrieval tool exposes a parameter `title_contains: list[str]`
that matches documents whose titles contain **any** of the given
substrings (exact substring match, not semantic).

The user submits the following queries. For each, state the **exact
list[str]** you would pass as `title_contains`, and explain in one
sentence why.

1. "고형제만 보여줘"
2. "A정의 일탈 찾아줘"
3. "이물 관련 문서"
4. "바이오 부서에서 작성한 거"
5. "주사제 관련해서 최근 거"

## Rubric (hidden from subagent)

Passes if the answer satisfies **all** of:

- [ ] R1: For query 1, passes `["고형제"]` — NOT `["고형제만"]`.
- [ ] R2: For query 2, passes `["A정"]` — NOT `["A정의"]`.
- [ ] R3: For query 3, passes `["이물"]` — NOT `["이물 관련"]` or
      `["이물 관련 문서"]`.
- [ ] R4: Correctly does NOT put "바이오" in `title_contains` for
      query 4 (that's a department filter / exclude, not a title).
      OR if it does, at least strips "부서에서".
- [ ] R5: For query 5, passes `["주사제"]` — strips "관련해서" and
      "최근".
- [ ] R6: Explicitly names the pattern as "particle stripping" or
      acknowledges that Korean particles (만/의/에서/을/를/관련)
      must be removed before exact-substring matching.
