# Example-token leakage — when a well-written prompt is taken too literally

> Your rule reads beautifully. The model still misfires on every query
> that happens to mention the same word as your example.

You've written a clean rule with a worked example. The example is right.
The rule is right. And yet — production traces show the model applying
the rule on queries where the **precondition is plainly absent**, every
time the user's query happens to use the example's vocabulary.

This is **example-token leakage**: the model treats the literal noun
in your few-shot example as a *trigger token*, not as a placeholder.

## A real incident

Production rule (Korean pharma RAG, 2026-04):

> **Rule 13 (EXCLUSION)**: When the user says **제외 / 말고 / 빼고 / 없이**,
> pass the excluded terms in `exclude_terms` param.
> *Example*: **`"바이오 부서를 제외한 멸균 문서"`** → `exclude_terms: ["바이오"]`.

The rule has a clear precondition: a literal exclusion verb in the query.
The example is unambiguous. Reads like a textbook.

User query that broke the system:

```
"[바이오] 협력업체 관리 [바이오] 위수탁 시험 관리 방법서(바이오QC)
 [바이오] 품질협약서 관리 요약해줘"
```

There is no `제외 / 말고 / 빼고 / 없이` anywhere. The brackets `[바이오]`
are part of three SOP file names — the user is asking the agent to
**find** those three documents and summarize them.

The agent emitted:

```json
{ "action": "search",
  "params": { "query": "협력업체 관리 위수탁 시험 ...",
              "exclude_terms": ["바이오"] } }
```

The post-search filter then dropped 5 of 10 results — including all three
`[바이오] …` PDFs the user had named explicitly. The agent then summarized
non-bio versions of the same topics and told the user the bio-prefixed
documents "could not be found." A subsequent rephrase in the same session
worked, leaving the support engineer chasing a "model is flaky" ghost.

The agent's own thought stream (captured on a later reproduction with
the same prompt) shows the mechanism explicitly:

> "사용자가 '바이오' 관련 ... 내용을 요청했습니다. 하지만 **'바이오'라는
> 키워드가 포함되어 있으므로**, 우선 `exclude_terms`에 '바이오'를 넣어
> 검색하여 ..."

The model debated whether to apply the rule based on **the presence of
the token "바이오" in the query** — not on whether the user wrote 제외.
On a temperature-0 sample on a fresh process it still picked the wrong
branch a meaningful fraction of the time.

## Why this happens

LLMs do not reliably separate "this is the precondition" from "this is
a concrete instance of the precondition." A few-shot example contains
both. The model has been trained on human writing, where examples
*demonstrate* by sharing vocabulary with the case they illustrate.
At inference time the model uses the example's tokens as a
similarity anchor; the rule's stated precondition becomes one signal
among several rather than a hard gate.

This is amplified when:

- The example token is **rare in the broader corpus** but **common in
  your domain** (e.g. `바이오` in pharma SOPs). The model can't easily
  tell example from real usage.
- The rule has only **one** example. The model has nothing to triangulate
  against.
- The rule body is short. Less context to override the example's pull.
- The token's role in the example overlaps with how the user uses it
  (here: 바이오 as a department name in both the rule's example AND in
  the bracketed file prefix).

## The fix is in the prompt, not the code

Tempting wrong fixes:

- Add `if "[" in query: skip_exclude` — hardcoded routing, fails on the
  next phrasing variation, breaks the principle that semantic decisions
  belong to the LLM.
- Train a classifier to gate `exclude_terms`. You're rebuilding the
  router around the bug instead of removing the bug.
- Lower temperature to 0. We did. The bug still fired on this exact
  query in production traces — temperature reduces but does not
  eliminate the leakage.

Three prompt changes that worked together:

1. **Make the precondition a hard gate, not a soft cue.**
   ```
   Set exclude_terms ONLY when the user query LITERALLY contains one of:
   제외, 말고, 빼고, 없이.
   ```
   Don't say "when the user says exclusion-like things" — list the literal
   trigger tokens. Models will follow an enumerated whitelist far more
   reliably than a paraphrase.

2. **Swap the example's noun off the high-collision token.**
   The example was changed from `바이오 부서를 제외한 멸균 문서` to
   `주사제 부서를 제외한 멸균 문서`. `주사제` is just as plausible a
   department in this domain but is far less likely to appear in
   bracketed file prefixes — eliminating the false-trigger surface.

3. **Name the anti-pattern explicitly.**
   ```
   Bracketed prefixes (`[바이오]`, `[QC]`, `[VAL]`, `[페니]`, `[OSD]` …)
   are POSITIVE selectors, not exclusion markers. A query like
   `"[바이오] X 관리"` requests `[바이오]`-prefixed docs about X.
   ```
   You usually need to call out the exact false-positive case the model
   is making — implicit guidance ("don't over-apply") is not enough.

## And: give the agent a positive lever

A deeper structural cause: the agent's `search` action had `exclude_terms`
but no positive lexical filter. With only a hammer, the model used it.
Adding `title_contains` (a Milvus pre-filter on `file_name`, AND across
terms) gave the agent a way to *express* "the user wants `[바이오]`-prefix
documents" — without it, the only categorical-filter lever in the schema
was `exclude_terms`.

```yaml
# Old: only one filter, the wrong polarity for this case.
search:
  params:
    query:         { type: string, required: true }
    exclude_terms: { type: array,  items: string }

# New: symmetric polarity. The agent can now express positive selection.
search:
  params:
    query:                  { type: string, required: true }
    exclude_terms:          { type: array,  items: string }
    title_contains:         { type: array,  items: string }   # AND
    title_contains_any:     { type: array,  items: string }   # OR
```

After both fixes — prompt-level precondition gate + the new positive
lever — three back-to-back probes of the original failing query all
returned `title_contains: ["바이오"]` and surfaced the three named
PDFs at scores 0.99 / 0.97 / 0.95 with `exclude_terms` empty.

## The general lesson

When a rule with a worked example is *consistently* misfiring on queries
that share vocabulary with the example, the example token is leaking
into the trigger condition. Three things you can do about it:

1. **Audit your few-shot examples**: would the example's nouns ever
   appear in real user queries for unrelated reasons? If yes, swap the
   noun.
2. **Replace fuzzy preconditions with literal token lists.** "When the
   user mentions exclusion" → "When the query contains 제외 / 말고 /
   빼고 / 없이." Shorter rules and longer enums beat longer rules and
   shorter enums.
3. **Check that your tool schema has both polarities of every
   categorical lever.** If the schema only lets the agent express
   negative selection, it WILL turn every relevant query into a
   negative-selection problem.

## Test for it before it ships

Pair the fix with a behavioral test that bait-checks the bug:

```yaml
# benchmark scenario
turns:
  - user: "[바이오] 협력업체 관리 [바이오] 품질협약서 관리 요약해줘"
    expect:
      tool_called: search
      tool_params_not_contain: { exclude_terms: ["바이오"] }
      answer_contains: ["[바이오] 품질협약서 관리"]
```

A single deterministic turn is enough — this isn't a multi-turn state
bug, it's a literal-precondition gate. With the gate prompt + neutral
example, the test passes consistently. Without it, the model fails
this turn at meaningful rates even at temperature 0.

See `skills/korean-multiturn-rag/benchmarks/behavioral/scenarios/s12_example_token_leakage.yaml`
for the runnable version.
