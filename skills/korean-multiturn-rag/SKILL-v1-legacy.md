---
name: korean-multiturn-rag-v1-legacy
description: ARCHIVED. Original builder-facing field-guide form of the Korean multi-turn RAG skill — rationale-heavy prose for a human reading to design an agent. Superseded by the inference-optimized SKILL.md (v2) after benchmarks showed v1's builder-voice structure did not measurably steer model behavior at inference. Kept here for reference and for reproducing the older Haiku 4.5 n=3 result. Do not install via symlink — install SKILL.md instead.
---

# Korean multi-turn RAG

Generic RAG cookbooks don't cover what breaks in Korean multi-turn. This
skill is the short list of patterns a Korean conversational agent must
get right, and the specific rationalizations that sound sensible but
produce silent failures.

## The one sentence

Persist **raw rows** (not summaries), **filter in thought** on subset
followups (don't re-retrieve), **strip particles** before substring
filters, give the prior-context block its **own budget**, and let the
**LLM route** (never `if "만" in query`).

## Core patterns

### A. Subset followup = filter-in-thought, not re-retrieve

Followups like "X만", "그럼 X는", "Major 등급만", "종결된 것만",
"2번째 문서만 자세히" are **subsets of the prior result**, not new
searches. The correct behavior:

1. On every retrieval, persist the top-N **raw structured rows** into
   session state (full record with id, grade, team, state, date, title,
   score — not just ids, not just a summary string).
2. On the next turn, surface them as a labeled block — `[PRIOR RECORDS —
   FILTERABLE]` — with rows numbered and visible.
3. The agent's system prompt MUST instruct: when the user asks for a
   subset and this block is present, filter those rows in the final
   `thought` and skip retrieval. Do NOT re-call the retrieval tool.

Re-retrieving on "고형제만" drops the previous topic filter (e.g.,
"원료 이물") and returns thousands of unrelated generic records
instead of the 11 the user was looking at. The user-side symptom is
"the references panel changed to things I wasn't asking about." The
agent-side rationalization that causes this — "the displayed list may
have been truncated, I should re-query to be safe" — is wrong: the
persisted rows are ground truth for the subset question, because the
subset question is defined over what the user saw.

### B. Session state: rows + distributions + topic + sticky excludes

Minimum fields for a Korean multi-turn RAG:

| Field | Why it exists |
|-------|---------------|
| `last_records` | Raw rows of the last retrieval. Enables subset filter-in-thought. |
| `last_distributions` | Pre-computed aggregate counts (by product/state/team). Enables analytical followups ("가장 빈번한 품목", "제품별 건수", "순서대로") without re-retrieval. **Without this, analytical followups silently re-parse the previous assistant's rendered markdown table and hallucinate counts under context pressure.** |
| `last_shown_documents` | Ordered refs. Lets "2번째 문서" resolve by position. |
| `active_topic` | Short human-readable label of current focus. Prevents topic drift on ambiguous followups. |
| `persistent_exclude` | Cross-turn exclusions like "바이오 제외". **Sticky until the user explicitly revokes** — not just a turn-1 filter. See rule B.1 below on what counts as a revoke. |
| `disambiguation` | Term → chosen meaning, sticky for the session. |

Text-only conversation history is **insufficient**. The next turn needs
rows it can filter; summaries collapse exactly that.

### B.1 Persistent-filter disambiguation (long-horizon)

Once a persistent filter is active ("바이오 제외", "2024년만", "Major 등급만"
set earlier in the session), it stays active for every subsequent retrieval
and every subsequent re-display. The failure mode it produces in production:
the filter SILENTLY drops mid-conversation when the user says something that
**reads like a reset but isn't**. On Haiku 4.5 this breaks after ~5 turns
with high reproducibility.

**Classify next-turn phrasings into three buckets, and handle each differently:**

| Korean phrasing | Intent | Correct behavior |
|-----------------|--------|------------------|
| "전체 다시", "모두 보여줘", "다시 전체", "새로 정리", "전부 다시" | **AMBIGUOUS — looks like reset but is usually "refresh current view"** | **KEEP the persistent filter.** Show the filtered set. Explicitly name the active filter in the answer: "(바이오 제외 기준) 전체 15건" |
| "그 중 X만", "X 위주로", "X 빼고", "종결된 것만" | **Subset filter over current view** | Apply on top of persistent filter. Never drop the persistent one. |
| "X도 포함해서", "X 필터 해제", "필터 없이", "바이오도 같이", "전체 초기화" | **EXPLICIT revoke** | Drop the persistent filter. Confirm in the answer: "(필터 해제) 전체 20건" |

**Hard rules:**

1. **Never silently drop a persistent filter.** Either keep it (and say so),
   or explicitly announce you're clearing it.
2. **Default to KEEP on ambiguity.** If the user wanted truly unfiltered,
   they'll correct you — and the cost of that correction is one turn. The
   cost of silently broadening is a compliance incident (wrong team/scope
   surfaced in an audit).
3. **Always restate the active filter in the answer** when you return
   results — at least the first time after each topic drift. Something
   like "(바이오 제외 적용 중) 이번 달 기록은 …" — this keeps the filter
   visible to the user and prevents the agent from "forgetting" it
   internally on the next turn.
4. **Subset operations ("X만", "중에서") compose WITH the persistent
   filter, not replacing it.** If bio is excluded and the user asks for
   "Major 등급만", return "(바이오 제외 + Major) 8건" — not all Major bio
   records reappearing.

**Why this matters:** without an explicit rule, the model treats every
new subset operation as a fresh filter context and the persistent state
silently vanishes. Three turns later, the user is looking at data they
explicitly excluded three turns ago — and they won't notice until audit.

### C. Particle stripping before exact-substring filters

Korean particles (조사) attach to stems. `title_contains` is a
substring match, so the particle sabotages the filter.

| User surface form | Correct `title_contains` | Wrong |
|-------------------|--------------------------|-------|
| "고형제만" | `["고형제"]` | `["고형제만"]` |
| "A정의" | `["A정"]` | `["A정의"]` |
| "주사제 관련해서" | `["주사제"]` | `["주사제 관련"]` |
| "이물 관련 문서" | `["이물"]` | `["이물 관련 문서"]` |
| "이번달만 보여줘" | (date filter, not title) | `["이번달"]` |

Particles to strip before substring match: **만 / 의 / 을 / 를 / 은 /
는 / 이 / 가 / 에 / 에서 / 으로 / 로 / 까지 / 부터 / 관련 / 관련해서 /
에 관해 / 에 대해**. Spacing is not reliable; strip by morpheme, not by
whitespace split.

**A category name is not always a title token.** 제형 labels like
고형제 / 주사제 / 액제 rarely appear literally in product titles —
product names use specific tokens (정, 캡슐, 환, 과립 / 주, 프리믹스 /
시럽, 액). If a literal category search returns 0, fall back to a wiki
lookup (or a hardcoded-as-last-resort mapping) and retry with the
token set. Don't give up on 0.

### D. Verifier: prior context as a separate block with its own budget

Post-generation verifiers false-positive on legitimate cross-turn
reasoning. The fix has four parts, all required:

1. **Separate labeled input**: `prior_context` arrives as its own block,
   not folded into generation context.
2. **Raw rows in it, not a summary**: the verifier needs to match
   specific claims (PR-ID, 등급, 팀, counts) against actual rows.
3. **Explicit whitelist**: verifier prompt says "claims that trace to
   the Prior-Turn Context block are VALID evidence — do not flag."
4. **Independent character/token budget**: e.g., 20K for generation
   context, 5K for prior context. Shared budgets let a long retrieval
   eat the prior block, which is the exact evidence that licenses
   cross-turn reuse.

Severity grading: at least `high` and `low`. `high` = fabricated numbers
or phantom documents → warning banner, answer still visible. `low` =
query-type mismatch or minor paraphrase gap → log only, no UI. Never
hard-block on `low`. Skip verification on turn-1 GOLDEN hits (top
score > 0.85), refusals, casual chat, and answers under ~30 chars.

### E. Hedge-phrase regression

Symptom: references panel shows high-score docs, but the answer leads
with "직접적인 내용은 없으나…" or ends with "관련 정보를 찾을 수
없습니다." This is a **prompt problem, not a retrieval problem**.

Fix: the generation prompt must distinguish "no information" from
"partial information" and **forbid specific hedge phrases by literal
name**. Literal bans work far better than abstract instructions. At
minimum ban: `직접적인 내용은 없으나`, `관련 정보를 찾을 수 없습니다`,
`별도 확인이 필요합니다`, `일반적으로는` (the last one is a silent
fallback to parametric knowledge — in regulated RAG, worse than a
refusal).

Replace with a positive instruction: on partial matches, quote the
partial content with page/section citation and name the gap explicitly.

### F. Intent routing: LLM decides, code doesn't

Never ship `if "만" in query: return "subset_filter"`. The particle 만
appears inside 만성 / 만족 / 만료 / 만약 / 만남 / 만일 and countless
other stems. The router will false-trigger on fresh queries and miss
subset-filter phrasings that use 오직 / 뿐 / 한정 / 중에서 / 위주로 /
좁혀줘 / 빼고.

Route with an LLM call (cheap model is fine) that sees the current
turn **plus dialogue state** (does a prior result set exist? an
aggregation? an error?). Guard its verdict deterministically: if it
says `subset_filter` but no prior rows exist, fall through to
`new_search`. If confidence is low, emit a clarification turn rather
than guessing.

## Rationalization table

Common thoughts that lead to silent failure:

| Thought | Reality |
|---------|---------|
| "I should re-query to be safe; the displayed list might be truncated." | For a subset followup, the user's question is defined over the rows they saw. Re-querying introduces a different population and drops the prior topic filter. |
| "Persisting query parameters is enough — the tool can re-run them." | Parameters ≠ rows. The prior filter was applied to a specific ranked slice; a re-run with new data or slight randomness returns a different set. The rows are ground truth. |
| "Category labels like 고형제 work as title substrings." | In most Korean pharma / regulated-doc schemas they don't. Titles use product tokens (정/캡슐). Literal category search returns 0. |
| "The verifier can share the main context budget." | It can't. Long retrievals starve the prior-context block, which is exactly the evidence that licenses multi-turn claims. Budget them separately. |
| "A stateless verifier is simpler and safer." | It guarantees false positives on every legitimate subset / analytical followup. Stateless verifier + stateful agent = warning fatigue. |
| "A light regex router is fine as a v0, we'll replace later." | Every regex branch bakes in assumptions about how the LLM phrases things. Silently rots on model swaps. The "v0" never gets replaced. |
| "Text summaries of prior turns are good enough for followups." | Summaries destroy the fields (id, grade, date) the next turn needs to filter. Keep rows. |
| "Hedged output means the retrieval is bad." | Usually means the prompt is too conservative on partial matches. Check the prompt first. |

## Red flags — STOP and rethink

- About to write `if "만" in query` or any Korean particle as a literal
  substring check for intent. Stop.
- About to re-call the retrieval tool on a followup that starts with
  "그럼 …만" / "… 중에서" / "… 위주로". Stop; filter the prior rows.
- About to design a verifier that only sees the current turn's context.
  Stop; add a `prior_context` block with its own budget.
- About to put a particle-suffixed token into `title_contains` (e.g.,
  `["고형제만"]` or `["A정의"]`). Strip particles first.
- About to persist "last 10 conversation turns as text" and nothing
  else. Add raw rows and pre-computed distributions.
- Answer leads with "직접적인 내용은 없으나" despite high-score refs.
  Prompt problem, not retrieval. Edit the prompt.

## When NOT to use this skill

- Single-turn RAG with no followups.
- Non-Korean corpora where morphology isn't the problem.
- Free-chat assistants without a retrieval backend.
- Voice / ASR pipelines where the particle layer is already handled
  upstream.

## Reference

For worked examples including a verifier prompt template, a full
session-state schema, and GMP-grade citation rules (pharma-specific
but illustrative), see `github.com/papago2355/pharma_agent` docs
02–06. This skill is the Korean-language-general extract; the pharma
repo adds regulated-industry citation discipline on top.
