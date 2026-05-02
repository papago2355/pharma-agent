# 멀티턴 탈출(escape) 규칙

`02-bug-patterns.md`의 패턴 1–3은 *단일* 후속 턴에서 깨지는 것들을
다룬다 — 검색이 넓어지고, 검증자가 오탐하고, 톤이 헷지된다. 이 챕터는
에이전트가 **여러 턴에 걸쳐** 막혀 있는데도 막힌 것을 인지하지 못할 때
일어나는 일들을 다룬다: 같은 막다른 토픽을 계속 재검색, 직전 답변을 새
답변인 양 재진술, 두 턴 전 stale state를 "방금 받은 결과"인 양 노출.

stateless 검색은 이걸 스스로 빠져나오지 못한다. 에이전트에게는 다음이
필요하다:

1. **신호** — 세션 상태에 "이미 시도했고 안 됐다"를 턴 사이에 살아남는
   형태로 둘 것.
2. **규칙** — 시스템 프롬프트가 그 신호들을 읽고, 검색 루프를
   재시작하는 게 아니라 *멈추게* 할 것.
3. **품위 있는 종료** — 에이전트가 멈춰야 한다고 옳게 판단했을 때, 14자
   고정 문자열이 아닌 무언가가 응답할 것.

이 챕터는 이 셋을 모두 다룬다. 패턴들은 코퍼스 도메인에 무관하다 — 매
턴마다 에이전트가 다시 검색할 수 있게 둔 모든 대화형 RAG에서
재현된다.

## 규칙들이 노리는 세 가지 실패 모드

| 실패 | 사용자가 보는 것 | 에이전트가 하는 것 |
|---|---|---|
| **Hedge 루프** | 같은 헷지 응답 "X에 대한 정보를 찾을 수 없습니다"가 3턴 연속 | 같은 토픽으로 같은 검색을 재실행. 매 재시도가 같은 저관련도 결과를 돌려준다. |
| **Search decay** | 점수 그래프가 0.82 → 0.71 → 0.58 → 0.41로 떨어짐. 최종 답변은 일반론. | 매 턴 약간 더 넓은 쿼리로 피벗, 점수는 떨어지고, 에이전트는 escalate하지 않는다. |
| **Short-followup paraphrase** | 사용자: "말한 거야" / "다시" / "맞나?" → 에이전트가 직전 답변을 동의어로 다시 렌더링 | 짧은 후속 턴을 "직전 답을 부연하라"로 해석. 정답은 "차별화하거나 escalate". |

세 경우 모두 **재검색은 틀린 동작**이다. 옳은 동작은 **escape** —
이미 시도했음을 사용자에게 정직하게 말하고, 우리가 가진 것을 보여주고,
다른 방향을 묻는 것.

## 신호 층 — 규칙들이 읽는 4개의 세션 상태 필드

`03-session-state-design.md`의 기본 테이블 위에 다음을 추가한다. 모두
**턴 종료 시점**에 채우는 파생 신호다(턴 시작이 아니다).

| 필드 | 타입 | true가 되는 시점 |
|---|---|---|
| `last_answer_was_hedge` | `Optional[bool]` | 직전 답변이 정직한 no-info / out-of-scope였을 때. `None`은 "모름"(검증자가 안 돈 경우). 절대 `False`로 기본값을 잡지 말 것. |
| `last_strategy` | `str` | 플래너가 어떤 전략을 골랐는지 (`direct_lookup`, `subset_filter`, `analytical` 등). 차별화 규칙이 사용. |
| `search_history` | `List[Dict]`, cap 3 | 최근 턴별 한 항목씩: `{top_score, ref_count, strategy}`. "직전 두 턴이 저관련도였다"를 규칙이 직접 읽게 한다. |
| `last_answer_summary` | `str`, ≤ 200자 | 직전 답변의 **순수 head 트렁케이션**. 정규식으로 "verdict line"을 뽑아내려고 하지 말 것. 짧은 후속 규칙이 paraphrase 감지에 사용. |

`last_answer_was_hedge`는 네 필드 중 가장 자주 잘못 설계되는 필드다.
유혹은 답변 텍스트에 정규식을 거는 것이다(`"확인되지 않[음습]"`,
`"범위 밖"`, …). 하지 말라. 에이전트는 자기 헷지 표현을 매번 달리
표현하고, 정규식은 빗나가고, 세션 상태는 *자신만만하게 잘못된*
상태로 끝난다 — `None`보다 나쁘다. 신호는 다음 절의 검증자 스키마
필드에서 가져오라.

## 검증자 듀얼 신호: `is_hedge` vs `is_dead_end_escape`

챕터 04는 검증자를 단일 boolean(`pass`)으로 다룬다. 운영 멀티턴에서는
**두 개의 독립 필드**가 추가로 필요하다 — 둘 다 검증자가 판정한다:

```json
{
  "pass": true,
  "is_hedge": true,
  "is_dead_end_escape": false,
  "severity": "low",
  "reason": "..."
}
```

- `is_hedge`: 답변이 정직한 no-info였는가? **`pass`와 독립** — 정직한
  no-info도 *passing* 답변이다, 단지 다음 턴 상태로 전파해야 할 뿐.
- `is_dead_end_escape`: 답변이 "이미 검색했고 실패했다"는
  *escalation*이었는가? **`is_hedge`와도 독립** — dead-end escape는
  "내가 시도한 건 이거다, 다른 각도를 줘"이고, hedge는 "모르겠다"이다.

다음 턴의 다른 규칙들이 각각을 트리거 신호로 쓴다:

- `is_hedge` → **hedge-loop escape** 규칙 (같은 토픽 재검색 금지).
- `is_dead_end_escape` → 회귀 테스트 타깃 (replay 테스트가 에이전트가
  실제로 정직한 dead-end에 도달했는지, 그저 헷지만 한 게 아닌지를
  검증).

왜 분리하는가: 두 신호를 하나의 `is_no_info: bool`로 합치면, 정당한
hedge에도 dead-end escape에도 똑같이 true가 박혀, 에이전트는 "지금은
escape 해야 한다"와 "방금 hedge했다"를 구분할 수 없다. 분리는 스키마
필드 하나 추가하는 비용이고, 다운스트림에서 얻는 명확함은 크다.

## 세 개의 규칙

각 규칙은 위에서 정의한 신호만 읽는다. 각 규칙은 시스템 프롬프트에
**문장 두 개** + 후속 템플릿에 한 줄 — 그 이상은 안 된다.

### 규칙 A — Hedge-loop escape

```text
HEDGE-LOOP ESCAPE: last_answer_was_hedge가 true이고 현재 턴이
last_answer_summary와 같은 토픽을 묻고 있다면, 재검색하지 말 것.
final_answer를 호출하되 thought에서 dead-end를 정직하게 명명하고
대안 방향을 제안할 것. 표현은 자유롭게 — 고정 문자열을 복사하지
말 것.
```

트리거: `last_answer_was_hedge=true` + LLM이 인라인으로 하는 토픽
유사도 판단.

### 규칙 B — Search-decay escape

```text
SEARCH-DECAY ESCAPE: search_history의 마지막 3개 중 최소 2개가
top_score < 0.6 이고 ref_count <= 2 이면, 같은 토픽의 paraphrase를
다시 검색하지 말 것. final_answer로 escalate.
```

트리거: cap-3 `search_history` 버퍼에 대한 집계. 시맨틱이 아니라
**숫자** — 에이전트가 직접 읽을 수 있는 *스코어보드 사실*이다.

### 규칙 C — Short-followup differentiation

```text
SHORT-FOLLOWUP DIFFERENTIATION: 사용자 턴이 30자 미만이고
last_answer_summary가 비어 있지 않으면, 답변은 last_answer_summary와
**반드시 차별화**해야 한다. paraphrase 금지, re-render 금지.
새 정보가 없다면 규칙 A로 escape.
```

트리거: 단순 길이 + 존재 체크, 뒤에 행동 지침. `< 30자` 컷오프는 실측
실패 모드와 일치한다("말한 거야" — 5자, "다시 보여줘" — 7자).

**알려진 정제 포인트**: `< 30`은 무해한 인정 응답에서 over-fire 한다
("확인했어요", "다음 질문"). 두 가지 강화 방향:

- 임계를 `< 20자`로 좁히고 명시적 의도 체크("사용자가 같은 것을 다시
  묻고 있다")와 페어. 더 빡센 규칙, 오탐 적음.
- `< 30`은 유지하되 직전 두 턴에서 `active_topic`이 일치할 때만 발화.
  대화의 자잘한 추임새에서 규칙이 발동하지 않게 한다.

데이터에 맞는 변형을 선택하라. 둘 다 정직하다 — 첫 번째가 약간
보수적, 두 번째가 약간 자유롭다.

## 상태 위생: 0-결과 턴에서 sticky 키를 명시적으로 비울 것

어떤 턴이 0건을 돌려주면, sticky 세션 키들(`last_records`,
`last_distributions` — 스키마 이름 무엇이든)을 **비워라**. "직전 턴
그대로 두기"는 안 된다.

이것이 막는 버그:

```
턴 1: 검색 → 11건 → last_records = [11행]으로 세팅
턴 2: 검색 → 0건 → ??? last_records를 그대로 두면?
턴 3: 사용자 "그 중 X만" → 에이전트가 turn 1의 last_records를
     "방금 받은 결과"로 필터링 → 잘못된 답변
```

검증자는 이걸 잡지 못한다 — 턴 1의 행들은 *턴 2에서는* 유효한 직전
컨텍스트지만, *턴 3에서는* stale이다. 에이전트는 상태가 명시적으로
비워지지 않으면 둘을 구분할 길이 없다.

```python
if result.records:
    session.last_records = result.records
else:
    session.last_records = None   # 또는 .pop / del
```

`else` 브랜치 한 줄이 전체 픽스다. 어렵지 않다. 어려운 건 그걸 쓸 걸
**기억하는** 것이다.

## 인스턴스별 dedup, 리스트별 dedup이 아니다

도구 층이 전체 파라미터 셋을 해시해서 호출을 dedup한다면, 다음 트릭이
그걸 무력화한다:

```
호출 1: document_fetch(files=[A])         # hash(A)         → 새 호출
호출 2: document_fetch(files=[A, B])      # hash(A,B)       → 새 호출
호출 3: document_fetch(files=[A, B, C])   # hash(A,B,C)     → 새 호출
```

세 호출 모두 풀 파라미터 해시 기준으로는 "구분되는 호출"이라, 파일
`A`가 세 번 fetch된다. 에이전트가 악의적이지도 않았다 — 매 턴 진짜
새 파일을 추가했고, dedup이 매번 `A`를 통과시켰을 뿐이다.

수정: 호출별이 아니라 **인스턴스별**로 dedup. 이 루프에서 이미 fetch
된 파일들을 `Set[str]`로 추적하고, 실행 시점에 파라미터를 그 셋에
없는 파일들로만 필터:

```python
fetched_files: Set[str] = set()

for action in plan:
    if action.name == "document_fetch":
        new_files = [f for f in action.params["files"]
                     if f not in fetched_files]
        if not new_files:
            continue   # 호출 자체를 스킵
        action.params["files"] = new_files
        fetched_files.update(new_files)
    execute(action)
```

배치 도구 일반에 적용된다(`document_fetch`, `bulk_lookup`, multi-id
`record_get` …). 리스트별 dedup이 매혹적인 이유는 명백한 테스트 케이스가
통과하기 때문이다 — `[A]` 다음 `[A]`는 정확히 스킵된다. `[A]` →
`[A,B]` → `[A,B,C]` 경로는 자기만의 테스트가 필요한데, 대부분의 팀은
그 테스트를 안 쓴다.

## 품위 있는 종료: 캔드 문자열이 아니라 LLM이 작성

대부분의 팀이 기본으로 깔고 가는 no-results 경로:

```python
if not result.has_data():
    return "검색 결과를 찾지 못했습니다. 다른 키워드로 시도해 주세요."
```

**정직하지만 쓸모없다.** 운영 데이터에서 본 회귀 실패 4건 중 3건이
이 경로에 앉아 있었다 — 에이전트는 검색했고, 못 찾았고, 그러나
사용자의 직전 턴들에 캔드 문자열이 surface하지 못한 멀쩡한 대안들이
있었다.

LLM 호출로 대체하되, 출력을 **두 개의 모양 중 하나**로 제약하라:

- **(A) 정직한 no-match + 세션 상태에 앵커된 대안.** `shown_documents`
  + 최근 3개 검색 요약 + 위키(있다면)에서 후보를 끌어온다. *"정확한
  X는 찾지 못했지만, 이전에 본 Doc-A / Doc-B 가 관련될 수 있습니다.
  어느 쪽을 보시겠어요?"*
- **(B) 정직한 no-match + 구체적 옵션이 있는 명확화 질문.** *"X를
  찾지 못했습니다. Y(영역) 또는 Z(영역)를 의미하셨나요?"*

핸들러 입력:

```python
compose_graceful_no_results(
    query=original_query,
    shown_documents=session.shown_documents,
    recent_searches=session.search_history,   # cap 3
    agent_thoughts=last_react_thoughts,       # 선택, 효과 큼
)
```

Fail-soft: LLM 호출이 실패하거나 빈 문자열을 돌려주면, 짧고 정중한
시스템 메시지로 폴백하라 — 절대 조용히 `""`를 렌더하지 말 것.
폴백은 짧아도 되지만("다시 한 번 명확히 말씀해 주세요."), **본
경로가 아니라 백업**이다.

이 챕터에서 가장 leverage 높은 변경이다. 회귀 실패 3건을 깨고서야
여기 도달했지만, 다른 팀들은 한나절이면 같은 패턴을 복사할 수 있다.

## 안티패턴: 정해진 한국어 문구를 verbatim 출력시키기

문자열 함정이다. 예를들어:

```yaml
# 시스템 프롬프트 규칙 (이걸 ship하지 말 것)
dead-end escape일 때, 최종 답변은 반드시 "이미 검색했으나" 라는
정확한 문자열로 시작해야 한다 — harness가 결정적으로 dead-end
escape를 탐지할 수 있도록.
```

이건 **프롬프트와 harness를 파멸적으로 결합**시킨다. 따라오는 두 가지 실패 케이스:

1. LLM이 다르게 표현한다("이전에 검색해 보았으나…", "이미 확인한
   결과…"). harness 정규식이 빗나간다. 정당한 escape를 escape가
   아니라고 플래그한다.
2. 프롬프트 규칙이 에이전트의 표현을 고정 문구로 제약한다 — 이건
   "라우팅은 LLM에 맡기라" 원칙이 경고하는 바로 그 패턴이다, 이번엔
   쿼리-측이 아닌 **답변-측**에서.

수정: verbatim-string 요구를 프롬프트에서 최대한 금지하라. **검증자**가 답변이
dead-end escape인지 판정하게 하고(`is_dead_end_escape: bool`),
harness는 검증자 신호를 읽게 하라 — 답변 substring을 매칭하는 게
아니라.

같은 교훈이 정리할 수 있다: "프롬프트가 에이전트에게 특정 한국어
문자열을 emit하라고 시켜서 다운스트림 시스템이 그걸 탐지할 수 있게
한다" — 이런 패턴을 발견하면, LLM이 verbatim 재현하지 않아도 되는
경계에서의 **구조화 신호**로 바꾸라.

## 종합 — 체크리스트

### 파라미터를 기준으로 하는 경우(예시)
- [ ] 검증자가 `is_hedge: bool`, `is_dead_end_escape: bool`를 스키마
      필드로 emit, **`pass`와 독립**.
- [ ] 세션 상태에 `last_answer_was_hedge`(Optional, 검증자 source —
      *절대* 정규식 X), `last_strategy`, `search_history`(cap 3),
      `last_answer_summary`(head 200자).
- [ ] 시스템 프롬프트에 위 4개 신호를 읽는 escape 규칙 3개.
### 일반적인 체크 리스트(예시)
- [ ] 0-결과 턴에서 sticky 세션 키를 명시적으로 비움.
- [ ] 배치 도구 dedup이 **인스턴스별**(셋 멤버십)이지, **호출별**
      (파라미터 해시)이 아님.
- [ ] no-results 경로가 LLM-작성 graceful 핸들러를 호출하고, 정중한
      fail-soft 폴백을 가짐.
- [ ] 다운스트림 탐지를 위해 verbatim 한국어 문자열을 emit하라고
      에이전트에게 시키는 프롬프트 규칙은 없음. 모든 시스템 간 신호는
      구조화된 검증자 필드.

에이전트가 멈춰야 할 때 멈추고, 가진 것을 surface하고, 가진 게 없을
때 다른 각도를 묻는다 — 멀티턴 UX의 나머지는 이 위에 쌓인다. 이게
없으면 다른 멀티턴 패턴들은 모두 수면 아래 누수를 막는 패치일 뿐이다.
