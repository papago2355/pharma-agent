# Verifier cross-turn context

A post-generation verifier that only sees the *current* turn's context will
false-positive on every followup that legitimately reasons over prior-turn
data. The answer quotes "11건" from turn 1; turn 2's retrieval came back
with broader records; the verifier can't find "11" in this turn's context
and flags the answer as fabricated.

The answer was right. The verifier was blind.

## Why verifiers should not be stateless

A verifier is checking *the answer*, not *the retrieval*. And answers
span turns. In a multi-turn agent, a final answer is legitimately allowed
to reuse:

- Counts and distributions from the prior turn's structured search.
- Specific record fields (PR-ID, 등급, 팀, 일자) from prior rows the user
  asked to filter.
- Disambiguation the user accepted earlier in the session.

If the verifier only sees this turn's generation context, all three look
like hallucinations. A stateless verifier under a stateful agent is
guaranteed to cry wolf.

## Prompt template that accepts prior context

The prompt needs two clearly labeled evidence blocks:

```text
## User Query
{query}

## Prior-Turn Context (from earlier in this conversation — also VALID evidence)
{prior_context}

## Generation Context (what the LLM saw)
{context}

## Generated Answer
{answer}
```

And rules that explicitly whitelist cross-turn reuse:

```text
DO NOT flag:
- Claims that can be traced to the Prior-Turn Context block. E.g., on a
  subset-filter followup like "고형제만", the 11건 total from the
  previous turn IS valid evidence — the answer may filter those prior
  rows without re-searching.
- Total record counts pre-computed by the search system (the search is
  already filter-scoped; the reported total IS the count for that filter).
```

Without the whitelist, LLM verifiers default to "numbers I can't find
locally = fabricated" and will override even clear prior-context traces.

## What goes into `prior_context` — raw records, not summaries

The instinct is to pass a text summary: "last turn showed 11 records
about 원료 이물 일탈." Don't. The verifier needs the *rows* so it can
match the answer's specific claims (PR IDs, grades, dates, titles)
against them. A summary collapses exactly the information the verifier
needs to cross-check.

Pass the same structured block the agent already got:

```text
[PRIOR QMS RECORDS — FILTERABLE]
Source query: 원료 이물 일탈
Records: 11

  [1] PR-xxxxx | Major | xxxx팀 | 종결 | 2025-03-31
      xxxxx정 xx/xxxmg xxxxx 원료 이물 발견 건
  [2] PR-xxxxx | Major | xxx팀 | 종결 | 2025-02-14
      ...
```

Plus prior structured distributions (product/state/team counts) when the
followup is analytical.

## When to skip verification

Verification is a second LLM call. Spend it where it matters.

- **Turn 1 with GOLDEN-score hits** (top retrieval > 0.85, query is
  literal): skip. The answer is either a direct quote or a refuse; a
  verifier adds latency without catching anything.
- **Casual chat / greetings**: skip. No factual claims to verify.
- **Short answers (< 30 chars)**: skip. Not enough surface area for a
  meaningful hallucination.
- **Explicit refusals** ("해당 정보는 확인되지 않습니다"): skip. The
  answer is making no claim.

Everywhere else — especially multi-turn followups and analytical
questions — verification is cheap insurance.

## Severity grading so the UI doesn't cry wolf

Two levels in practice:

| Severity | Trigger | UI behavior |
|----------|---------|-------------|
| `high` | Fabricated numeric values or phantom document names | Prepend a warning banner, keep the answer visible |
| `low` | Query-type mismatch, minor unsupported paraphrase | Log only, do not surface |

Never hard-block a response on verifier output. The verifier is a
second opinion, not an oracle. It will misfire on valid paraphrase,
on Korean↔English translation of terms, and on reasonable inferences.
A hard block on low-severity issues trains users to ignore the banner
when it matters.

Default to `pass=true`. Only fail when the verifier can point to a
**specific claim** and confirm it is absent from both the current
context and the prior-turn context.

## Budget: cap prior context separately

Do not share a single character budget between generation context and
prior context. If a followup's retrieval returns a long document, a
single budget lets it eat the prior-records block, which is exactly
the evidence the verifier needs.

In production we cap them independently: ~20K chars for the generation
context, ~5K chars for the prior-turn context. Distributions + 20 record
rows fit comfortably in 5K. Prior context should never starve to make
room for raw retrieval, because the whole point of the block is to
license reuse across turns.

## A concrete failed case

Before the fix:

- Turn 1: "최근 원료 이물 일탈 목록" → agent finds 11 PRs, shows them.
- Turn 2: "고형제만 추려줘" → agent correctly filters the 11 prior rows
  in `final_answer.thought` (no re-search), yields 4 rows.
- Verifier sees only turn 2's context (empty — the agent skipped search).
- Verifier: "답변에 PR-xxxxx, Major, 생산1팀 등이 나오지만 컨텍스트에
  근거가 없습니다." → WARN banner.

The user sees a correct answer with a scary warning that says it might
be fabricated. Trust damaged; answer was fine.

After the fix (prior context wired into the verifier):

- Same flow, but the verifier also receives the `[PRIOR QMS RECORDS —
  FILTERABLE]` block.
- Every cited PR ID, grade, and team traces to a row in prior context.
- Verifier: PASS.

The code change was small (pass `prior_context` into
`verify_agent_output`; add the whitelist rule to the prompt). The
bug was a *design* omission: the verifier was built before multi-turn,
and stayed single-turn when the agent didn't.

## Summary

- Verifiers are stateless by default; multi-turn agents are not. Fix
  that mismatch explicitly, not incidentally.
- Pass prior context as a separate, labeled evidence block with its
  own character budget.
- Pass raw records, not a summary. Summaries destroy the very detail
  the verifier needs to match.
- Default to `pass=true`; grade severity; never hard-block on `low`.
- Skip verification on turn 1 GOLDEN hits and casual chat — not
  everywhere.
