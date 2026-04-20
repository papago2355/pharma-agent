# Pharma-specific patterns for agentic RAG

Regulated-industry RAG has rules the generic cookbook doesn't cover.
Citations must survive an audit. Deviations, CAPA, and change control
have canonical vocabularies. "Close enough" answers aren't just less
useful — they have compliance consequences. This page is the set of
patterns we wish we'd had on day one.

The stack we shipped runs against a Korean pharma company's SOP corpus
and a structured QMS database. Most of what follows generalizes to any
regulated vertical with a document taxonomy (legal, finance, medical
device), but the examples are pharma.

## QMS data structure: filter-first, not semantic-first

QMS is not a document corpus. It's a **small fixed-taxonomy table**:

- 일탈 (deviation)
- CAPA (corrective and preventive action)
- 변경관리 (change control)
- 시정조치 (corrective action)
- 소비자불만 (consumer complaint)

Each record has structured fields: PR-ID, grade (Major/Minor/Critical),
team, state (진행/종결/반려), created_date, product, title.

Semantic search over this table is the wrong default. The user asking
"이번달 Major 일탈" does not want a nearest-neighbor search on "Major
일탈" — they want `WHERE grade='Major' AND table='일탈' AND date_from=
<this month>`. Semantic retrieval on QMS is a fallback for the *title*
field only, after structured filters have been applied.

Design rule: the agent's QMS tool takes `table_filter`, `grade`,
`team`, `state`, `date_from/to`, `title_contains[]`, `exclude_terms[]`
as first-class parameters. Only `title_contains[]` is semantic; the rest
are exact filters. SOP tools, by contrast, are semantic-first —
different taxonomy, different tool.

## SOP citation discipline: three fields or don't cite

An audit-trace citation needs all three:

1. **Document number** — e.g., `<COMPANY>-SOP-xxxx`. The primary key in the
   SOP registry.
2. **Version** — rev. A/B/C, or the effective date. Without this,
   "cited an SOP" means nothing; the section numbering and content
   change between revs.
3. **Section** — e.g., `5.1.4항`, `Appendix 2`. Points the auditor to
   the exact clause.

Missing any one of these and the citation is unauditable. Bake the
three-field requirement into the generation prompt, into the reference
panel schema, and into the verifier's checklist.

Bad: "SOP에 따르면..."
Bad: "변경관리 절차에 명시되어 있다..."
Good: "<COMPANY>-SOP-xxxx (Rev. B) 5.1.4항: '...'"

## Dosage-form fallback lives in a wiki, not in code

Korean pharma categorizes products by 제형 (dosage form): 고형제,
주사제, 액제, 반고형제. These category labels almost never appear
literally in product titles. A tablet titled "A정 10mg" is 고형제
but the word "고형제" does not appear in the title — the product-name
token "정" does.

Mapping:

- 고형제 → 정 / 캡슐 / 환 / 과립
- 주사제 → 주 / 주사 / 프리믹스
- 액제 → 시럽 / 액 / 점안
- 반고형제 → 연고 / 크림 / 젤

Do **not** hardcode this mapping in the retrieval service. Two reasons:

1. It changes. New product lines introduce new tokens; the regulatory
   taxonomy shifts between revisions.
2. Hardcoded mappings rot silently after LLM swaps — see bug pattern
   #5 on hardcoded routing.

Put it in a wiki page the agent consults with a `wiki_lookup` action
when a literal category search returns 0. The correct flow:

1. Try the literal category as the user wrote it (`title_contains=
   ["고형제"]`) — respect user wording, fail fast.
2. On 0 results, call `wiki_lookup(query="제형 분류")`.
3. Retry with the token set the wiki returned.
4. In the final thought, explain the substitution so the user sees
   that the search was broadened deliberately, not randomly.

This keeps domain knowledge in a single editable place, keeps the
agent honest about what it did, and stays robust to model swaps.

## Change-control chain: reason about upstream state

A single piece of regulated information lives in a chain of documents:

    제품표준서 → 마스터 제조 지시 및 기록서 → 실제 제조 배치 기록서

A query like "이 제품 제조 공정 바뀌었나?" cannot be answered by
semantic search on the current state document. The agent must reason
about upstream: what's the current 제품표준서 revision, which master
record cites it, what change-control PR authorized the change.

For the agent, this means recipe design with **document-kind awareness**:

- When the query references a *change*, search 변경관리 table first
  (the change log), then walk to the cited product standard.
- When the query is a process question, search the product standard
  first, then surface the most recent change-control record referencing
  it.

A naive "search everywhere, rerank" approach either misses the change
record (drowned by product-standard chunks) or misses the product
standard (drowned by change tickets). The chain has to be walked
explicitly.

## The QMS subset-filter pattern

The most valuable pattern we shipped. Covered in depth in docs 02 and
03; restating here with the pharma framing because the pattern *matters*
in QMS specifically — regulators will ask "show me deviations about
원료 이물, then just the 고형제 ones, then just the ones closed in
Q1." Every refinement is a subset of the prior result, not a new
question.

Three parts:

1. **Persist raw records** in session state after every QMS search.
   The top-N rows of `pr_id / grade / team / state / date / title`.
2. **Surface them in prev_context** as a `[PRIOR QMS RECORDS —
   FILTERABLE]` block on the next turn.
3. **Filter in thought** — the agent's system prompt has a rule that
   says: if the user asks for a subset and the prior-records block is
   present, filter those rows in `final_answer.thought` and do not
   re-search.

Re-searching on "고형제만" loses the 원료 이물 topic filter and
returns 5529 generic records instead of the 11 the user was looking at.
The whole pattern exists to prevent that single failure mode, and in
QMS it is the #1 source of user rage.

## GMP-aware answer formatting: when to refuse, hedge, answer

A regulated answer has three acceptable shapes.

### Answer (with citation)

The retrieved content directly and unambiguously covers the question.
Quote the relevant section verbatim with document number, version, and
section. No hedging language. No "일반적으로".

### Hedge (with partial citation)

The retrieved content partially covers the question — e.g., the SOP
specifies a tolerance range but not the exact value the user asked
for. Say so explicitly:

> <COMPANY>-SOP-xxxx 5.1.4항에 허용오차 기준이 기술되어 있으나, 사용자가
> 문의한 특정 구성품에 대한 구체 수치는 해당 조항에 명시되지 않았습니다.
> 관련 수치는 배치 기록서 또는 품질 기준서를 확인해야 합니다.

The hedge names the gap and points to where the gap can be closed.

### Refuse (usefully)

The retrieved content does not cover the question at all. The refusal
is not "모릅니다." The refusal **points to the nearest SOP** the user
should consult instead:

> 해당 주제에 대한 직접 문서는 확인되지 않았습니다. 관련 가능성이
> 있는 문서는 <COMPANY>-SOP-xxxx (교정관리) 및 <COMPANY>-SOP-xxxx (측정장비
> 유지관리)이며, 구체적인 측정 절차가 필요하시면 해당 문서를
> 확인해 주십시오.

A bare "no info" refusal is compliance-safe but user-hostile. A refusal
with a pointer is both.

The anti-pattern to watch for is the Korean hedge "직접적인 내용은
없으나, ..." appearing in an answer that actually *does* cite relevant
content. That's not hedging — that's an LLM over-applying a
conservative rule to partial-match content. See doc 05 (Korean NLP
gotchas) for the prompt fix.

## Evidence trail the system should log

For every regulated answer, the system should be able to reconstruct:

- Which tool calls the agent made, with parameters.
- Which documents and record IDs were retrieved, with their scores.
- Which subset of those was surfaced in the generation context.
- Which claims in the answer trace to which evidence.
- Verifier output (PASS/WARN + reasons).

Store this per session, retention at least matching the regulator's
audit window. When the auditor asks "why did the system tell the user
X on that date?", you need to be able to answer from logs alone.

## Summary

- QMS is a typed table. Filter first, search second.
- SOP citations require document number + version + section. All three.
- Dosage-form and similar mappings belong in a wiki the agent reads,
  not in code.
- Document chains (제품표준서 → 제조 기록) must be walked explicitly;
  flat reranking won't recover them.
- Subset-filter followups in QMS need persisted raw records and a
  filter-in-thought rule, or regulators will get 5529 irrelevant PRs
  instead of the 11 they asked about.
- Answer in one of three shapes — answer, hedge, useful refusal.
  Never bare "no info".
- Log the full evidence trail per session. Audits will ask.
