# Extreme user — a 17-turn Korean multi-turn conversation

> What a real production conversation actually looks like when a user
> who knows the corpus drives an agent through search, drilldown,
> comparison, re-framing, and role-play generation — all in one
> session. All identifiers anonymized (`특정 절차문서 A` / `B`,
> `관련 분야`, etc.). Turn-level Korean wording preserved verbatim;
> only the agent-side answer column is summarized into one sentence
> per turn.

## Why this counts as "extreme"

- **17 turns**, no clean topic break — the user keeps the conversation
  alive end-to-end.
- **Five distinct task shapes** in one session: SOP discovery, doc-
  anchored drilldown, comparison, semantic re-framing, and role-play
  Q&A generation.
- **Eight short followups** under 20 characters
  (`관련 분야 문서로 보라고.` / `그 문구 어디 있냐고.` /
  `그 기준으로 질문 뽑아.` …) — each one a place where the agent
  has to differentiate, not paraphrase.
- **Three explicit re-frames** the agent has to absorb without
  losing prior scope: T9 (`출발물질을 원료로 보고`), T11
  (`절 번호 빼고 내용만`), T16 (`특정 절차문서 A라니까`).
- **Two persistent constraints** that have to survive across turns:
  the active document anchor (`특정 절차문서 A` and later `B`) and
  the running list of "5 items" the user asked about at T7.

If your agent makes it through this without dropping the doc anchor,
collapsing the 5-item list into a different set of items, or
re-rendering an earlier answer when the user types `관련 분야 문서로
보라고.`, you're in good shape.

## Conversation log

### Phase 1 — SOP discovery (T0–T3)

| #  | 질문                                            | 답변                                              |
|---:|-------------------------------------------------|---------------------------------------------------|
|  0 | 협력업체랑 위수탁 시험, 품질협약서 관리 SOP 찾아줘.    | 관련 SOP 후보와 각 문서의 주요 관리 범위를 설명했다.            |
|  1 | 청정등급 구역 정기점검 SOP 찾아.                   | 청정등급 설정 구역의 환경점검 및 유지관리 관련 SOP와 대응 내용을 설명했다.   |
|  2 | 청정구역/청정등급 설정 기준 문서로 정리해줘.            | 청정구역 구분 및 청정등급 설정·관리 기준을 설명했다.                |
|  3 | 이 항목들 SOP에서 어떻게 관리되는지 대조해.             | 요청 항목별 관련 SOP와 주요 관리 내용을 대조해 설명했다.            |

User progressively expands scope: outsourcing → clean-area inspection
→ classification standards → cross-compare across SOPs. T3 expects the
agent to remember "이 항목들" refers to the items implicitly accumulated
across T0–T2. Connects to **`docs/03-session-state-design.md`** —
`active_topic` and `last_records` need to be alive across all four
turns for T3 to land.

### Phase 2 — Doc-anchored drilldown (T4–T8)

| #  | 질문                                            | 답변                                              |
|---:|-------------------------------------------------|---------------------------------------------------|
|  4 | 특정 절차문서 A에서는 이거 어떻게 관리돼?               | 특정 절차문서 A 기준으로 환경관리 항목들이 어떻게 규정되는지 설명했다.       |
|  5 | 원자재 외관 확인, 관리번호, 먼지 제거 내용 있는 SOP 찾아.  | 원자재 입고 시 확인·표시·보관 절차와 관련된 SOP 후보를 설명했다.        |
|  6 | 관련 분야 문서로 보라고.                            | 관련 분야의 원자재 입고 관리 문서를 기준으로 일부 항목의 확인 여부를 설명했다.  |
|  7 | 이 5개가 특정 절차문서 B에 적용되는지 봐.              | 요청한 5개 항목과 특정 절차문서 B의 관련 내용을 비교해 설명했다.         |
|  8 | 방금 5개, 특정 절차문서 B 기준으로 다시 정리해.          | 특정 절차문서 B 기준으로 요청 항목별 적용 여부와 관련 서술을 설명했다.      |

T4 introduces a **persistent doc anchor** (`절차문서 A`); T6
(`관련 분야 문서로 보라고.` — 11 characters) is a short followup
that's actually a *scope adjustment*, not a new question. T7 introduces
a **5-item list** that has to stick across T7–T13. T8 is a short
followup that filter-refines the same 5 items by a new doc anchor (B).
Connects to **`docs/09-multi-turn-escape-rules.md` §B.1** — the
sticky-filter durability rule applies to doc anchors and item lists
exactly as it applies to `바이오 제외`-style filters.

### Phase 3 — Re-framing and disambiguation (T9–T13)

| #  | 질문                                            | 답변                                              |
|---:|-------------------------------------------------|---------------------------------------------------|
|  9 | 출발물질을 원료로 보고 다시 찾아.                    | 출발물질을 원료로 해석해 관련 항목을 재검색·재검토한 내용을 설명했다.        |
| 10 | 저 5개 항목 현재 관리 절차만 요약해.                  | 특정 절차문서 B에 따른 현재 관리 절차를 항목별로 요약했다.            |
| 11 | 아니, 절 번호 빼고 내용만 간단히.                    | 조항 번호 중심이 아니라 절차의 의미를 바탕으로 간략히 요약했다.          |
| 12 | 그 문구 어디 있냐고.                               | 해당 문구의 직접 일치 여부와 관련 취지의 존재 여부를 설명했다.          |
| 13 | 그러니까 문서 보고 책임지고 5개 항목 관리방식 써.        | 특정 조직의 원자재 관리 방식으로 해석해 5개 항목을 요약 설명했다.        |

The hardest phase. T9 is a **disambiguation lock-in** —
"출발물질 := 원료 for the rest of this conversation." T11 is a
**style-only modifier** (`아니, 절 번호 빼고 내용만 간단히.`) — the
agent must keep the same content + 5-item list and only change
formatting. T12 is a **prior-claim reference** (`그 문구`) —
the agent has to resolve "that phrase" against its own previous
answer. T13 is a **frustrated re-statement** of T10 with stronger
wording. Connects to **`docs/05-korean-nlp-gotchas.md`** (T9
disambiguation), **`docs/09-multi-turn-escape-rules.md` Rule C**
(T11/T12/T13 are all short followups that must differentiate from
the previous answer rather than re-render it), and **`docs/02-bug-
patterns.md` pattern 1** (the "thinking log > final answer" gap is
extra dangerous in this phase because the agent's reasoning has
to stitch together the doc anchor, the item list, and the
disambiguation simultaneously).

### Phase 4 — Role-play Q&A generation (T14–T16)

| #  | 질문                                            | 답변                                              |
|---:|-------------------------------------------------|---------------------------------------------------|
| 14 | 특정 절차문서 B에서 사원급 질문이랑 답 만들어.          | 실무자가 현장에서 물어볼 만한 질문과 그에 대한 답변 예시를 생성했다.       |
| 15 | 앞전 특정 절차문서 A도 똑같이 해.                    | 이전 절차문서를 기준으로 실무자 관점의 질문·답변 예시를 생성했다.         |
| 16 | 특정 절차문서 A라니까. 그 기준으로 질문 뽑아.           | 특정 절차문서 A 수행 중 실무자가 즉시 확인할 만한 질문 예시를 제시했다.    |

T15 (`앞전 특정 절차문서 A도 똑같이 해.`) is the agent's first chance
to swap the active doc anchor from B back to A. T16 is the user
correcting because the agent didn't fully swap on T15 — a perfect
example of how a short followup can mean "do exactly what I just said,
but actually do it this time." Connects to the **case-2 perspective-
collapse pattern** in `docs/bugs/...` (in the parent project) and to
**Rule C** of chapter 09: short followups must not be treated as
"keep going with the previous frame."

## What this demonstrates

A multi-turn agent that ships only the **chapter 03** session-state
basics will fail somewhere between T6 and T13. To survive the full
17 turns, the agent needs:

1. **Persistent anchors** for the active doc and the running 5-item
   list, surviving short scope-adjustment followups (T6, T8).
2. **Sticky disambiguations** carrying T9's `출발물질 := 원료` through
   T10–T13.
3. **Differentiation on short followups** (T11, T12, T13, T16) —
   never re-render a prior answer because the user typed something
   short.
4. **Honest frame transparency** when the agent's reasoning sees
   nuance the user didn't ask for (Phase 3 in particular) — name the
   frame, don't collapse silently.

If you build for this conversation, the standard "first three turns
look great in a demo" failure modes go away on their own.
