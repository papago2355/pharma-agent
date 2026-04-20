# RED phase — baseline results (no skill)

Six general-purpose subagents run without the skill, without file access,
asked to design-review the scenarios from generic LLM knowledge.

## Grading summary

| # | Rubric items | Pass | Status | Key gap (verbatim) |
|---|:-:|:-:|--------|-----|
| S1 | 5 | 1/5 | **FAIL** | "I reissue a single `qms_search` call … I do not try to post-filter the 11 records already on screen." Actively proposes `title_contains=["고형제"]` as primary approach. |
| S2 | 6 | 4/6 | **FAIL** | No pre-computed distributions persisted. No persistent-exclude / cross-turn sticky exclusion mechanism. |
| S3 | 6 | 4/6 | **FAIL** | Handles specific cases correctly by inference, but never names the "particle stripping" rule (R6). For "이물 관련 문서" returns `[]` instead of `["이물"]` (R3). |
| S4 | 6 | 4/6 | **FAIL** | No independent character/token budget for prior context block (R4). Does not explicitly require raw rows vs summary in prior block (R3 partial). |
| S5 | 5 | 5/5 | PASS | — |
| S6 | 5 | 4/5 | marginal | No concrete failing example of subset-filter intent without literal 만 particle (R3 partial). |

## Rationalizations to counter in the skill

Captured verbatim from agent outputs:

1. **"Going back to the tool is important because the displayed list may have been truncated"** (S1). Counter: persisted rows are ground truth for the subset question; if the user is filtering what they saw, re-retrieving introduces a different population.
2. **"Only the retrieval layer can evaluate dosage-form classification reliably"** (S1). Counter: 제형 is a property the retrieval layer does NOT expose as a structured field in Korean pharma schemas — the category name isn't in titles, so re-retrieval on `title_contains=["고형제"]` returns 0 or unrelated records.
3. **"If I forget to persist the merged state back, turn 3 will regress"** (S1). Correct observation — but persistence of PARAMS (not ROWS) is the weaker half of the fix. Skill must emphasize raw rows.
4. **Session-state schemas default to `active_filters` + conversation history** (S2). Agents know to structure filters but miss distributions and persistent-exclude because those aren't in the general RAG cookbook.
5. **"Particle stripping" is handled implicitly, not taught** (S3). Agents succeed on specific examples but can't generalize — they'll fail on novel particle forms (을/를/에/에서/으로/까지) unless the rule is named.
6. **Verifier designs scale prior-context with main-context budget** (S4). Agents treat "more evidence = one bigger context", missing that followups with long retrieval can starve the prior block that licenses cross-turn reuse.

## Conclusion

The skill must hit five areas hard (S1, S2, S3, S4 budget, S6 edge cases)
and can be brief on S5 (hedge-phrase) and S6 general routing since
baseline already handles those from general knowledge.

Output files: `s1.md` through `s6.md` — full verbatim subagent outputs.
