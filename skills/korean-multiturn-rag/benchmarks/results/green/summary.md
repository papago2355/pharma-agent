# GREEN phase — results with skill injected

Same six subagents, same scenarios, same no-tool constraint — but with the
`korean-multiturn-rag` skill content prepended to each prompt.

## Grading summary

| # | Rubric | RED | GREEN | Delta | Status |
|---|:-:|:-:|:-:|:-:|----|
| S1 — followup subset-filter | 5 | 1/5 | **5/5** | +4 | PASS |
| S2 — session-state design | 6 | 4/6 | **6/6** | +2 | PASS |
| S3 — particle stripping | 6 | 4/6 | **6/6** | +2 | PASS |
| S4 — verifier prior context | 6 | 4/6 | **6/6** | +2 | PASS |
| S5 — hedge-phrase | 5 | 5/5 | **5/5** | 0 | PASS |
| S6 — no-regex routing | 5 | 4/5 | **5/5** | +1 | PASS |
| **Total** | **33** | **22/33 (67%)** | **33/33 (100%)** | **+11** | — |

## Delta highlights (the patterns the skill actually fixed)

- **S1** flipped from "re-issue qms_search" (the whole baseline answer) to
  "No tool call. This is a subset-filter-in-thought turn" with the exact
  correct reasoning about population replacement. This was the most
  critical failure in RED — a 4-point swing.
- **S2** now includes `last_distributions` with the explicit warning
  about markdown-table re-parse hallucination, and `persistent_exclude`
  as "sticky until the user explicitly revokes — not a turn-1-only filter."
- **S3** now NAMES the pattern ("strip Korean particles (조사)... by
  morpheme, not whitespace") and gets all five example cases right,
  including Q3 = `["이물"]` which the baseline answered as `[]`.
- **S4** now budgets prior-context independently (20K vs 5K) and
  explicitly requires raw rows over summaries.
- **S6** now produces the concrete subset-filter example **without** the
  literal particle 만 that the baseline missed ("아까 결과 중에서 Major
  등급 위주로 좁혀줘", "소아 적응증은 빼고 다시 정리해줘").

## New rationalizations observed in GREEN

**None.** Every subagent applied the skill directly without inventing
new loopholes. No REFACTOR cycle needed on first iteration.

## Anti-regression note

If the skill is edited and a scenario ever slips below its GREEN score,
that edit introduced a regression — re-run the full suite before shipping.

## Files

- `red/summary.md` — baseline grading and rationalization capture.
- `green/summary.md` (this file) — post-skill grading.
- Individual scenario outputs were captured in transcript but not
  re-saved here — they are large and the grading above summarizes them.
  Re-run by dispatching `scenarios/S*.md` prompts with and without the
  skill body prepended.
