# Future plan

Docs currently marked TBD in the README, captured here as a roadmap so
contributors (including future-me) know what's next and what each piece should
cover. Numbered in the order I think they're most valuable to ship.

---

## 1. Verifier cross-turn context

**Working title:** `docs/{en,ko}/04-verifier-cross-turn.md`

**Problem this piece solves**
Post-generation verifiers that only receive the current turn's context false-
positive on every followup that legitimately reasons over prior-turn data.
The answer cites "11건" (from turn 1) and the verifier flags it as fabricated
because turn 2's retrieval returned different, broader records.

**What the doc should cover**
- Why verifiers should NOT be stateless — they're checking answers, and
  answers span turns.
- A minimal prompt template that accepts a `prior_context` section.
- How to decide what goes into `prior_context` (records? distributions?
  a summary?) — and why raw records beat summaries.
- When to skip verification entirely (turn 1 GOLDEN hits, casual chat).
- Severity grading so UI doesn't cry wolf on "low" warnings.
- Budget: prior context cap separate from main context cap, so cross-turn
  information can't starve evidence the answer is actually based on.

**Evidence to draw on**
- `backend/services/agent_verifier.py` before/after the fix.
- A specific failed case: session showing answer correct, verifier WARN,
  root cause = missing prior context.

---

## 2. Korean NLP gotchas for agentic RAG

**Working title:** `docs/{en,ko}/05-korean-nlp-gotchas.md`

**Problem this piece solves**
Korean morphology, particle attachment, and tokenizer variance quietly
sabotage pattern-matching approaches that work fine in English. Every
`if "X" in query:` branch has a silent failure mode on Korean input.

**What the doc should cover**
- Particle stripping (만/의/관련/에서/을/를) when building `title_contains`
  or other string filters. Examples: "고형제만" → "고형제".
- Why regex intent classification over Korean is a lost cause: morphological
  variants, spacing differences, homonyms.
- 제형 (dosage-form) category vs. product-name token mismatch:
  "고형제" almost never appears in titles → fall back to specific tokens
  (정/캡슐/환/과립) when the literal category returns 0.
- Hedge-phrase regression: Korean LLMs love "직접적인 내용은 없으나", which
  reads as "no info" even when the docs do contain partial info. How to
  write generation prompts that suppress this.
- Tokenizer edge cases: BGE-M3 vs tokenizers trained on Korean — why the
  same sparse embedding model can rank differently after a rebuild.
- A short list of terms that collapse to the same stem and break exact-match
  filters.

**Evidence to draw on**
- Memory notes: Korean particle tokenization, 제형 fallback, hedge-phrase
  removal from generation prompts.
- Real query → wrong filter cases from chat logs.

---

## 3. Pharma-specific patterns

**Working title:** `docs/{en,ko}/06-pharma-specific.md`

**Problem this piece solves**
Regulated-industry RAG has rules the generic RAG cookbook doesn't:
citations must survive audit, deviations and CAPA have canonical
vocabularies, and "close enough" answers fail in ways that have
compliance consequences.

**What the doc should cover**
- **QMS data structure**: 일탈 / CAPA / 변경관리 / 시정조치 as a small
  fixed table taxonomy. Why search over this table needs filter-first
  not semantic-first.
- **SOP citation discipline**: document number (<COMPANY>-SOP-xxxx), version,
  section (e.g., 5.1.4항) — all three required for audit-trace citations.
- **Dosage-form fallback**: how the "고형제 → 정/캡슐/환/과립" mapping
  should live in a wiki page the agent consults, not hardcoded.
- **Change-control chain**: 제품표준서 → 마스터 제조 지시 및 기록서 →
  실제 제조 — why an agent must reason about upstream document state,
  not just current state.
- **QMS subset-filter pattern**: "고형제만 추려줘" on prior deviation
  results — this is the pattern we shipped; explain the
  persist-records + surface-in-prev-context + filter-in-thought design.
- **GMP-aware answer formatting**: when to refuse, when to hedge, when
  to answer — and how to make the refusal itself useful (point to the
  nearest SOP instead of just saying "no info").

**Evidence to draw on**
- `backend/config/prompts/agent_system_prompts.yaml` rules 13–14a, 16.
- `backend/routers/chat_v2.py` session_state handoff code.
- Wiki pages around QMS taxonomy and dosage forms.

---

## Unprioritized / parking lot

Things that might become their own docs later, or might fold into the above:

- **Prompt versioning & rollback**: how to promote `rag_prompts_v6.yaml`
  safely when `_vN+1` regresses on some slice.
- **Agent budget & dedup guard**: why dedup keys should include the
  observation hash, not just action+params.
- **Wiki-augmented agents**: when to let the agent consult a wiki page
  vs. embed the page into retrieval vs. hardcode the knowledge.
- **SSE contract design**: event types, ordering guarantees, what to do
  when the stream dies mid-answer.
- **Multi-recipe planning**: sop_search → qms_search handoff, when to
  switch, how to enrich the second recipe with the first's output.

---

## How to pick up a topic

1. Claim it by opening an issue titled "draft: <topic>".
2. Write the EN doc first. Don't translate line-by-line — write the KO
   version as natural Korean tech writing (keep English terms like LLM,
   ReAct, observation; translate verbs and nuance).
3. Pair each pattern with at least one concrete symptom you'd see in
   logs or a UI screenshot — not just abstract advice.
4. Open PR; reviewers check both languages for parity of depth, not
   word-for-word match.
