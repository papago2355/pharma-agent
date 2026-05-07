# Hedge surface — "찾을 수 없습니다"가 게을러 보이지 않게

에이전트가 hedge를 결정하는 순간은 대화 전체에서 사용자가 가장
신뢰를 잃기 쉬운 지점이다. 사용자는 직전까지 loop trail — 검색
호출, 에이전트 thought, document_fetch — 을 보고 있다가 "정확히
일치하는 내용을 찾을 수 없습니다"를 받는다. trail이 풍성한데
답변이 빈약하면, 사용자는 그것을 정직으로 읽지 않는다. **에이전트가
포기했다**로 읽는다.

이 챕터는 hedge boundary에서 발생하는 세 개의 독립 실패 모드를
다룬다. 각 실패는 서로 다른 "게을러 보이는" 신호를 만들고, 서로
다른 surface에서 잡아야 한다.

1. **Loop thought ↔ 최종 답변의 모순** — 에이전트의 step thought는
   일치를 찾았다고 말하고, 최종 답변은 못 찾았다고 부정한다.
   사용자는 둘 다 본다.
2. **Hedge 옆에 붙은 오해의 인용** — 답변은 "찾을 수 없다"고
   말하고, 옆 인용 카드는 0.50점짜리 무관한 문서를 그대로
   보여준다.
3. **한 문장짜리 dismissal** — 4 step 검색과 thinking trail을 거친
   끝에 답변이 두 문장. 활동 대비 출력 불일치.

각 fix는 작다. 셋이 함께 land해야 hedge surface가 그것을 만들어낸
활동과 어울린다.

## 1. Verbatim-claim 모순

**증상**

사용자가 verbatim 규제 문구를 붙여넣고 "이거 어디 출처야?"라고
묻는다. 에이전트는 이렇게 진행한다:

```
Step 1 (search): "사용자가 입력한 문구가 포함된 문서를 검색한 결과,
  '<related-procedure-A>.pdf'와 '<related-procedure-B>.pdf' 두 건의
  관련 문서가 확인되었습니다."

Step 2 (document_fetch): "검색 및 문서 추출 결과, 사용자가 입력한
  문구와 정확히 일치하는 내용을 포함한 문서를 찾았습니다. ..."

최종 답변: "사용자께서 인용하신 문구는 사내 색인 어디에도
  등재되어 있지 않습니다."
```

사용자는 step 2 ("정확히 일치를 찾았다")와 최종 답변 ("색인에
없다")을 같은 UI에서 본다. 직접적인 모순이다. 답변 자체는 옳더라도
신뢰는 무너진다.

**왜 일어나는가**

에이전트의 step별 `thought`은 검색 결과의 *메타데이터*(file_name,
score, doc_id)에서 만들어진다 — chunk *텍스트*가 아니다. dense
similarity가 높은 두 SOP만 있어도 에이전트는 "exact match를
찾았다"라고 쓸 수 있다. 그 다음에 generation LLM이 실제 chunk
텍스트를 읽고, verbatim 겹침이 없다는 걸 보고, 옳게 hedge한다.

에이전트와 generation LLM은 같은 turn에서 서로 다른 evidence를
본다. 사용자는 두 출력을 다 보고, 서로 모순이라는 걸 보고, 둘
중 하나가 거짓이라고 결론짓는다.

이건 "topical 관련 ≠ verbatim 존재"라는 더 깊은 버그의 표면화다.
Dense retrieval은 *같은 주제* 문서를 찾는 데는 좋지만 phrase
search는 아니다. 에이전트의 thought이 둘을 혼동한다.

**해법 — VERBATIM-CLAIM HONESTY 규칙**

에이전트의 `thought` 내용을 게이팅하는 시스템 프롬프트 규칙을
추가한다.

> 사용자가 인용한 문구의 substantive 부분(한국어 ≥ 10자 또는 한
> 절)이 retrieve된 chunk 텍스트에 literally 들어 있지 않으면,
> `thought`에 "정확히 일치하는 내용을 포함한 문서를 찾았습니다" /
> "해당 문구는 …에 포함되어 있습니다" 등을 절대 쓰지 말 것.
>
> chunk가 topically 관련은 있지만 verbatim 텍스트가 들어 있지
> 않을 때는 그 사실을 명시한다: "주제는 일치하는 SOP는
> 확인되었으나, 인용 문구의 직접적인 포함은 청크에서 확인되지
> 않습니다."
>
> 규칙은 양방향이다 — 일치를 over-claim 하지 말고, topical chunk가
> 있는데 "아무것도 없다"고 under-claim 하지도 말 것.

왜 작동하는가: 에이전트가 *주제 관련성*과 *verbatim 존재*를 구분할
명시적 가이드를 받고, 사용자에게 stream되는 `thought`이 최종
답변과 같은 evidence에 grounded된다.

이건 프롬프트 규칙이지 에이전트 출력에 거는 정규식이 아니다.
사용자 substring이 chunk에 있는지는 LLM이 판단한다 — 우리가
판단하지 않는다.

## 2. 오해의 인용

**증상**

답변 본문은 "이 정확한 문구는 사내에서 확인되지 않습니다"라고
한다. 옆에 붙은 인용 카드는 `<unrelated-topic>.pdf` (점수
0.5038)을 보여준다 — 사용자 질문과 전혀 무관한 다른 주제의
문서다.

사용자는 점수 숫자를 읽지 않는다. hedge 답변 옆의 문서 카드를
보고 "에이전트가 자기 모순을 일으켰다" 또는 "이게 출처인데
에이전트가 놓친 것 같다" 둘 중 하나로 읽는다. 둘 다 틀린 해석이고,
둘 다 surface 책임이다.

**왜 일어나는가**

검색 retrieval은 관련도 threshold가 있다 (운영에서는 보통
rerank ≥ 0.40, "borderline relevant"로 calibrate된다). Reference
표시도 보통 같은 리스트를 그대로 쓴다. 그러나 retrieval 단계의
"borderline relevant"는 표시 단계에서는 "절대 출처는 아닌 문서"다.
사용자가 직접 보는 문서가 그 문서에 없는 관련성을 imply한다.

**해법 — 표시 floor를 retrieval floor와 분리**

User-facing emission 경계에서 numeric score floor를 적용한다
(BGE-reranker 출력 기준 ≥ 0.55가 경험적 floor). 순수한 데이터
validation이지 semantic decision이 아니다 — 한국어 string matching이
끼지 않는다. 전체 reference 리스트는 forensics용으로 그대로
기록되고, UI만 필터링된 버전을 본다.

```python
USER_FACING_REF_FLOOR = float(os.environ.get("USER_FACING_REF_FLOOR", "0.55"))
user_refs = [r for r in all_references[:10]
             if (r.get("score") or 0) >= USER_FACING_REF_FLOOR]
yield f"data: {sse({
    'type': 'search_done',
    'count': total_count,
    'references': user_refs,
    'retrieval_contents': retrieval_contents,
})}\n\n"
```

Retrieval threshold (우리는 0.40, "borderline relevant")는 LLM이
chunk를 reason하기에 적절한 floor다 — 약한 매치도 보고 판단해야
한다. 표시 threshold (0.55, "사용자에게 보일 만함")는 인용 카드에
적절한 floor다. 같은 데이터, 다른 두 소비자, 다른 두 floor.

이 fix는 프롬프트 규칙이 필요 없는 유일한 fix이기도 하다. Numeric,
deterministic, side-effect 없음. 이 챕터에서 한 가지만 가져간다면
이걸 가져가라 — 가이드 전체에서 hedge surface 개선에 가장 싼 fix다.

## 3. 한 문장짜리 dismissal

**증상**

4 step 검색, document_fetch 호출, 긴 thinking trail을 거치고, 최종
답변이:

> "검색된 SOP 내에 해당 문구와 정확히 일치하는 규정은 발견되지
> 않았습니다. 외부 규제 가이드라인 또는 사내 상위 규정의 일부로
> 보입니다."

두 문장. 사용자는 방금 ~12초 동안 에이전트가 "열심히 일하는" 걸
보고 있었다. 출력은 에이전트가 도중에 포기한 것처럼 읽힌다.

**왜 일어나는가**

대부분의 hedge-output 프롬프트는 방어적으로 작성된다 — "찾지
못하면 그렇게 말하라". logic은 옳지만, *길이*와 *모양* 신호가
틀렸다. 풍성한 활동 뒤에 따라오는 두 문장 dismissal은 결론이
옳더라도 게으르게 읽힌다.

비대칭이 하나 더 있다 — 성공 답변은 자연히 길다 (render할 내용이
있다). hedge는 내용이 없다. 그래서 default 생성은 짧은 hedge와
긴 성공을 만든다 — 즉 "hedge가 게을러 보임"은 프롬프트가 적극적으로
싸우지 않으면 시스템에 내장되어 있다는 뜻이다.

**해법 — substantive 5-part out-of-corpus 답변 shape**

코퍼스에 답이 없을 때, 답변은 그것을 만들어낸 활동과 매치되어야
한다. 5 part, 총 5–8 문장, 벽 같은 텍스트는 아니다.

1. **명확한 결론** (1 문장). 분명하게 진술. "상위 규정에 있을
   수도 있다"같은 모호한 hedge는 피한다. 조건부 wording — part 3에
   관련 문서 ≥ 0.55가 list될 예정이면 opening을 부드럽게 해서
   listing과 모순되지 않게 하고, 그렇지 않으면 강하게 유지한다.
2. **검색 범위** (1 문장). 사실로. 검색한 것의 이름 — SOP 색인,
   QMS 색인, 위키. 사용자는 "코퍼스가 bounded되어 있다"를 보아야지
   "에이전트가 무능하다"를 보면 안 된다.
3. **가장 가까운 사내 문서** — chunk 적어도 하나가 rerank ≥ 0.55
   AND 진짜 관련 토픽일 때만. 1–3개 list, 각각에 그 문서가 다루는
   것과 사용자 질문의 출처가 *아닌* 이유를 한 문장. 이 bar를 넘는
   chunk가 없으면 이 part 자체를 통째로 OMIT — 약한 인용으로
   padding 하지 말 것.
4. **추정되는 외부 출처** (1–2 문장). Wording이나 framing이 외부
   규제를 가리키면, 사용자 텍스트의 distinctive phrasing을 근거로
   가장 likely한 candidate를 명명. 특정 조항 번호, 고시 번호,
   개정 연도는 invent 하지 말 것.
5. **구체적인 next step** (1 문장). 명명한 외부 출처를 직접
   확인하라고 제안하거나, 사내에서 그 외부 규정의 implementation을
   찾고 싶다면 다른 키워드로 다시 물어보라고 제안.

"정확히 일치하는 규정은 발견되지 않았습니다" 한 줄로 끝내지
말 것. 검색한 것과 추정 외부 출처를 명명하지 않고 "다르게
물어봐"라고 추천하지 말 것. 추정 외부 출처를 짚을 수 없으면(part
4) 그 사실을 명시한다 — 규정을 추측하지 말 것.

이 shape는 verbatim 인용 lookup뿐 아니라 *모든* out-of-corpus
답변에 적용된다. 코퍼스에 토픽 자체가 없는 질문도, indexing되지
않은 doc을 요구하는 질문도 같은 템플릿이 동작한다.

## 세 fix가 어떻게 compose 되는가

각 fix는 다른 surface를 노린다.

| Fix | Surface | 종류 |
|---|---|---|
| VERBATIM-CLAIM HONESTY | 에이전트의 stream되는 `thought` | 프롬프트 규칙 |
| 표시 floor | Reference 카드 emission | 코드 (numeric, semantics 없음) |
| 5-part 답변 shape | Generation LLM 출력 | 프롬프트 규칙 |

모순(1)은 에이전트의 입력 경계에서 잡힌다. 오해의 인용(2)은 서버와
frontend 사이 SSE 경계에서 잡힌다. dismissal(3)은 generator의
출력에서 잡힌다. 셋은 state를 공유하지 않기 때문에 compose된다 —
각각이 독립적으로 land 가능하고, 어느 부분집합도 hedge surface를
개선한다.

세 fix가 모두 land한 후 사용자가 보는 것: 일을 했고, related-but-
not-matching 문서를 찾았고, 무엇을 검색했는지 명명했고, 추정 외부
출처를 명명했고, 구체적인 next step을 가리킨 에이전트. Hedge는
거절이 아니라 사용 가능한 답변이 된다.

## 이게 아닌 것

- **검색 개선이 아니다.** 붙여넣은 규제 문구는 코퍼스에 진짜 없다 —
  검색을 아무리 잘 해도 안 찾힌다. Fix는 표면에 있지 인덱스에
  있지 않다.
- **할루시네이션이 아니다.** Hedge 자체는 옳다. 버그는 옳은
  hedge가 어떻게 표시되느냐에 있다.
- **에이전트 출력에 거는 정규식이 아니다.** 표시 floor는 numeric
  (`score >= 0.55`); 한국어 string matching이 없다. 다른 두 fix는
  프롬프트 규칙이고, 매칭은 LLM이 판단한다 — 우리가 판단하지
  않는다.

## 진단 체크리스트

사용자 신고가 다음 중 하나면 바로 fix 하나로 매핑된다.

- "에이전트가 찾았다고 말하더니 못 찾았다고 했다" → fix #1.
- "인용된 문서가 내 질문과 무관하다" → fix #2.
- "에이전트가 너무 빨리 포기한 것 같다" → fix #3.

세 모두 사용자가 본 활동과 사용자가 읽은 표면 사이의 gap에 관한
것이다. gap은 surface마다 따로 닫는다.

## 챕터 09와 어떻게 맞물리는가

챕터 09는 escape *규칙*을 다룬다 — 에이전트가 재검색을 멈추기로
어떻게 결정하는가. 이 챕터는 에이전트가 escape를 옳게 결정한
*다음에* 일어나는 일을 다룬다. 둘은 sequential이다 — 09의 규칙은
에이전트에게 "멈추고 hedge로 final_answer 호출"이라고 말하고, 10의
surface 패턴은 그 hedge가 어떻게 표시되는지를 지배한다.

10 없이 09만 ship 하면 에이전트는 옳게 escape하지만 escape가
*게을러 보인다*. 09 없이 10만 ship 하면 surface는 polish되지만
에이전트는 여전히 dead end를 빙빙 돈다. 멀티턴 dead end가 거절이
아니라 답변처럼 느껴지려면 둘 다 필요하다.
