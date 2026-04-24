# 캐시-친화적 프롬프트 레이아웃 — 한 줄을 끝으로 옮긴 이야기

> `Today's date:` 한 줄을 시스템 템플릿 6번째 줄에서 맨 끝으로 옮겼다.
> Prefix cache 적중률이 ~1%에서 ~99%로 뛰었다. 같은 모델, 같은 답변,
> 운영 비용은 훨씬 저렴.

vLLM(과 대부분의 최신 OSS 추론 엔진)은 **자동 prefix caching**을 지원한다.
두 프롬프트가 토큰-prefix를 공유하면 엔진이 그 prefix의 KV-cache를
재활용하고, 갈라지는 tail에 대해서만 prefill을 돌린다. 옵트인하면
(`--enable-prefix-caching`) 무료고, 프롬프트 레이아웃이 친화적이기만
하면 된다.

함정: **캐시 fingerprint는 첫 번째 동적 토큰에서 갈라진다.** 프롬프트
상단 근처의 사소한 변수 하나 — 오늘 날짜, 사용자 이름, 요청 ID —
때문에 그 아래 모든 내용의 캐시 가능성이 무효화된다.

## 실제 before/after

프로덕션 에이전트 시스템 프롬프트 (한국 제약 RAG, 조립 후 ~22K chars):

**Before (전형적인 레이아웃):**
```
Line 1: You are a CKD pharmaceutical {domain_label} search coordinator.
Line 2: Your job is to find the right data — NOT to analyze ...
Line 3: A separate generation model will receive ALL your search results...
Line 4: <blank>
Line 5: <blank>
Line 6: Today's date: 2026-04-24                  ← DYNAMIC, 캐시 깨짐
Line 7: <blank>
Line 8: ## Recipe
Line 9: <recipe_yaml — 정적 액션 스키마 ~2,700 토큰>
...
Line 32+: ## Rules (정적 지시 ~5,000 토큰)
Line 120+: ## final_answer format ...
```

같은 recipe의 두 쿼리가 들어오면 프롬프트는 ~250 chars(1–5번 줄)까지
바이트 동일하다가 6번 줄(today's date)에서 갈라진다. vLLM의 prefix
cache는 첫 갈라짐 지점까지만 매치하므로, 호출마다 프롬프트의 ~99%가
**다시 prefill** 된다.

**After (한 줄 이동):**
```
Line 1: You are a CKD pharmaceutical {domain_label} search coordinator.
Line 2: Your job is to find the right data — NOT to analyze ...
Line 3: A separate generation model will receive ALL your search results...
Line 4: <blank>
Line 5: ## Recipe
Line 6: <recipe_yaml — 정적 액션 스키마 ~2,700 토큰>
...
Line 100+: ## Rules ...
Line 220+: ## Output Format ...
Line 230: ## Runtime Context
Line 231: Today's date: 2026-04-24                ← DYNAMIC, 이제 tail
```

같은 recipe의 두 쿼리에서 처음 ~22K chars가 바이트 동일하다. Prefix
cache 적중이 프롬프트의 ~99%를 덮는다. 모델이 받는 지시는 같고, 순서만
약간 다르며, 최종 답변은 변하지 않는다. 날짜-상대 쿼리("최근 한달간")도
정상 해결된다 — 날짜가 여전히 컨텍스트 안에 있고, 시작이 아니라 끝에
있을 뿐이다.

## "정적(static)"이 실제로 의미하는 것

캐시가 적중하려면 모든 게 모든 쿼리에 대해 문자 그대로 동일할 필요는
없다. 필요한 건 **캐시 슬롯을 공유하고자 하는 쿼리들 사이에서 동일한
토큰-prefix**다. 그 경계는 트래픽에서 어떤 쿼리들이 함께 군집하는지에
따라 달라진다:

- **같은 recipe + 같은 날짜의 모든 쿼리** → 캐시가 1번 줄부터 (날짜 줄
  직전까지) 덮는다. 일반적인 경우 — recipe는 안정적이고 날짜는 하루에
  한 번 바뀐다.
- **모든 쿼리(recipe 무관)** → 보편적인 서두만 캐시된다 (예시의 1–4번
  줄). recipe별 컨텐츠는 5번 줄에서 이미 갈라진다.
- **같은 사용자/역할/도메인의 모든 쿼리** → 사용자별 텍스트를 끼워 넣는
  지점까지 캐시.

일반 원칙: **자주 바뀌는 변수는 마지막에, 가장 큰 쿼리 군집이 공유하는
변수는 처음에 배치한다.**

## 복사해서 쓸 수 있는 레이아웃

```
[A. UNIVERSAL — 모든 호출에서 동일]
   역할 설명 (도메인 보간 없음)
   출력 포맷 예시
   일반적인 가드레일 (정직하라, 출처를 인용하라, ...)

[B. PER-RECIPE — 같은 recipe의 모든 쿼리에서 동일]
   도메인 라벨
   Recipe 스키마 (액션 파라미터, 허용 도구)
   규칙
   Final-answer 포맷

[C. PER-CALL — 매 요청마다 다시 렌더링]
   ## Runtime Context
   Today's date: {today}
   ## Previous Context (멀티턴인 경우)
   {SESSION_STATE block}
   {별도로 처리하지 않는 경우의 대화 이력}
```

블록 A는 모든 캐시 슬롯에 공유된다. 블록 B는 같은 recipe의 쿼리들에
공유된다. 블록 C는 매번 새로 만들지만 작다. 우선순위 순으로 정렬된 세
개의 캐시 계층 — 가장 많이 공유되는 컨텐츠가 먼저.

## 왜 이게 저평가됐나

대부분의 에이전트 코드베이스는 prefix caching이 출시되기 전에 작성됐거나
(또는 `--enable-prefix-caching` 플래그를 챙기지 않는 사람이 작성), 그래서
프롬프트 레이아웃이 역사적 가독성을 따른다 — "맥락을 설정"하기 위해
날짜와 사용자 정보가 위에. 모든 프롬프트가 새로 prefill되던 시절에는
타당했다. 오늘날에는 recipe를 쿼리들 간에 재사용하는 모든 에이전트
(거의 전부)에 대해 추론 비용을 ~10–100배 부풀리는 조용한 곱셈자다.

2분 변경, 에이전트 동작 변화 없음, 답변 품질 변화 없음, 프롬프트 컨텐츠
재구성 없음. 너무 작아 보여서 건너뛰게 되는 종류의 최적화이지만, 추론
청구서에서 가장 큰 라인 아이템 절감 중 하나가 된다.

## 효과 검증하기

세 단계로 변경의 양면을 모두 확인할 수 있다:

1. **엔진에서 켜져 있는지 확인**.
   `journalctl -u vllm | grep -i prefix-caching` 또는 systemd unit에서
   `--enable-prefix-caching` 확인. (SGLang은 보통 기본 켜짐.) 켜져 있지
   않다면 레이아웃 변경은 아무 효과 없음 — 플래그 먼저 켤 것.

2. **프롬프트가 실제로 정적인지 확인**.
   같은 recipe로 두 개의 다른 사용자 쿼리에 대해 시스템 프롬프트를
   렌더링하고 `diff`. runtime-context tail 외에는 모두 바이트 동일해야
   한다. 다른 게 다르다면(UUID, 랜덤 model_id 접미사, 밀리초 타임스탬프)
   찾아서 옮긴다.

3. **캐시가 적중하는지 확인**.
   `curl http://<vllm-host>:<port>/metrics | grep prefix_cache` —
   대부분 엔진이 적중률 메트릭을 노출. 또는 엔진 stdout grep:
   vLLM은 `Prefix cache hit rate: 51.6%` 같은 줄을 로깅. 절대값은
   트래픽 믹스에 따라 다르고, 봐야 하는 건 recipe를 반복하는 워크로드에
   대해 레이아웃 변경 후 적중률이 OLD up.

## 이게 고치지 못하는 것

Prefix caching은 **prefill** 컴퓨트를 재활용하지, **decode** 컴퓨트는
아니다. 출력이 길면(4K-토큰 final answer) decode 비용이 지배적이고
prefill 절감은 종단간 latency의 작은 비중을 차지한다. 효과가 가장
큰 경우:

- 세션당 짧은 출력이 많을 때 (도구-호출 JSON을 내는 에이전트 ReAct
  스텝이 완벽한 예 — JSON은 짧고 프롬프트는 길고 prefill이 지배적).
- 많은 사용자가 같은 recipe를 공유할 때 (모든 사용자가 같은 제품에
  접속하는 멀티-테넌트 SaaS).
- 출력 대비 컨텍스트가 클 때 (모든 retrieval-augmented 에이전트).

Decode-bound 워크로드는 효과가 적다 — 그쪽은 speculative decoding이
관련 최적화.

## 그리고: 캐시 무효화를 프롬프트 컨텐츠와 묶기

이 레이아웃에서 미묘한 의존성이 떨어진다. recipe에서 캐시가 ~99%
적중하면, 모델은 사실상 *프로세스 시작 시점에 로딩된 프롬프트에
얼어붙는다*. 규칙을 편집하고 재시작을 잊으면, 진행 중인 쿼리들은 YAML이
디스크에 적힌 후에도 prefix에 대해 옛 프롬프트의 KV-cache를 받게 된다.

작은 완화책 — 프로세스 시작 시 프롬프트 + recipe 디렉토리를 해시하고
fingerprint를 로깅:

```python
def _compute_prompt_fingerprint() -> str:
    h = hashlib.md5()
    h.update(Path("config/prompts/system_template.yaml").read_bytes())
    for f in sorted(Path("recipes").rglob("*.yaml")):
        h.update(f.read_bytes())
    return h.hexdigest()[:8]

PROMPT_FINGERPRINT = _compute_prompt_fingerprint()
log.info("Prompt fingerprint: %s", PROMPT_FINGERPRINT)
```

답변-수준 캐시(에이전트 루프 결과 캐시 등)도 갖고 있다면 그 키에
fingerprint를 포함시켜라 — 프롬프트가 바뀌면 캐시된 답변도 자동으로
무효화된다. vLLM의 prefix cache 자체는 엔진 재시작에 클리어되고,
프롬프트 변경이라면 어차피 재시작이 필요하지만, fingerprint는 그
의존성을 명시적이고 감사 가능하게 만든다.
