# The hedge surface — making "not found" look honest, not lazy

When an agent decides to hedge, the user is in the most trust-fragile
state of the entire conversation. They have just watched the loop trail
— search calls, agent thoughts, document fetches — and now read
"couldn't find an exact match." If the trail looked rich and the answer
looks thin, the user does not read it as honest. They read it as the
agent giving up.

This chapter covers three independent failure modes at the hedge
boundary. Each produces a different "looks lazy" signal and is fixed
on a different surface:

1. **Loop-thought ↔ final-answer contradiction** — the agent's streamed
   step thought claims a match; the final answer denies it. The user
   sees both side by side.
2. **Misleading citation next to a hedge** — the answer says "not
   found"; the reference card next to it shows a 0.50-score document
   anyway.
3. **One-sentence "couldn't find" dismissal** — after four search
   steps and a thinking trail, the answer is two sentences. Activity
   versus output mismatch.

Each fix is small. Together they make the hedge surface match the
activity that produced it.

## 1. The verbatim-claim contradiction

**Symptom**

A user pastes a verbatim regulatory passage and asks "where is this
from?" The agent runs:

```
Step 1 (search): "사용자가 입력한 문구가 포함된 문서를 검색한 결과,
  '시험기준 및 시험방법 관리 방법서.pdf'와 ... 두 건의 관련 문서가
  확인되었습니다."

Step 2 (document_fetch): "검색 및 문서 추출 결과, 사용자가 입력한
  문구와 정확히 일치하는 내용을 포함한 문서를 찾았습니다. ..."

Final answer: "사용자께서 인용하신 문구는 사내 색인 어디에도
  등재되어 있지 않습니다."
```

The user reads step 2 ("정확히 일치를 찾았다") and the final answer
("색인에 없다") in the same UI. Direct contradiction. Trust collapses,
even when the *content* of the final answer is correct.

**Why it happens**

The agent's per-step `thought` is generated from search-result
*metadata* (file_name, score, doc_id) — not the chunk *text*. Two
related SOPs ranking high on dense similarity is enough for the agent
to write "exact match found." Then the generation LLM, which reads the
actual chunk text, sees no verbatim overlap and correctly hedges.

The agent and the generation LLM use different evidence. The user sees
both outputs, sees them disagree, and concludes one of them is lying.

This is the deeper bug under "topic-relevant ≠ verbatim-present."
Dense retrieval is good at finding documents about *the same subject*.
It is not a phrase search. The agent's thought confuses the two.

**Fix — VERBATIM-CLAIM HONESTY rule**

Add a system-prompt rule that gates the agent's `thought` content:

> Do NOT state in your `thought` that you "found the user's exact
> quoted text" / "정확히 일치하는 내용을 포함한 문서를 찾았습니다" /
> "해당 문구는 …에 포함되어 있습니다" unless a substantive substring
> of the user's quote (≥ 10 Korean characters, or one full clause)
> literally appears in the retrieved chunk text.
>
> When the chunks are topically related but do NOT contain the
> verbatim text, say so explicitly: "주제는 일치하는 SOP는
> 확인되었으나, 인용 문구의 직접적인 포함은 청크에서 확인되지
> 않습니다."
>
> The rule applies in both directions: do not over-claim a match, and
> do not under-claim ("nothing found") when topical chunks DID return.

Why this works: the agent now has explicit guidance to distinguish
*topical relevance* from *verbatim presence*, and the `thought` it
streams to the user is grounded in the same evidence as the final
answer.

This is a prompt rule, not a regex check on the agent's output. The
LLM judges whether the user's substring is in the chunk; we do not.

## 2. The misleading citation

**Symptom**

The answer text reads "이 정확한 문구는 사내에서 확인되지
않습니다." The reference card next to it shows
`[SOP] 필터 밸리데이션.pdf` with score 0.5038 — a document about
filter validation, completely unrelated to the user's question about
suitability tests.

The user does not read score numbers. They read a doc card next to a
hedge answer and conclude either "the agent contradicted itself" or
"this is the source but the agent missed it." Both readings are wrong;
both are the surface's fault.

**Why it happens**

Search retrieval has a relevance threshold (often rerank ≥ 0.40 in
production, calibrated to "borderline relevant"). The display of
references typically reuses the same list. But "borderline relevant"
at the retrieval stage is "definitely not the source" at the
presentation stage. A doc the user can read with their own eyes is
implying relevance that the doc does not have.

**Fix — separate the display floor from the retrieval floor**

Apply a numeric score floor *at the user-facing emission boundary*
(empirically ≥ 0.55 for BGE-reranker output). This is pure data
validation, not a semantic decision — no Korean string matching
involved. The full reference list is still recorded for forensics;
only the UI sees the filtered version.

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

The retrieval threshold (0.40, "borderline relevant") is the right
floor for the LLM to reason over chunks — it should see weak matches
and decide what to do. The display threshold (0.55, "worth showing
the user") is the right floor for the citation card. Same data, two
consumers, two floors.

This fix is also the one that does NOT need a prompt rule. It is
numeric, deterministic, and side-effect-free. If you ship nothing
else from this chapter, ship this: it is the cheapest improvement to
the hedge surface in the whole guide.

## 3. The one-sentence dismissal

**Symptom**

After 4 search steps, document_fetch calls, and a long thinking
trail, the final answer is:

> "검색된 SOP 내에 해당 문구와 정확히 일치하는 규정은 발견되지
> 않았습니다. 식약처 가이드라인 또는 사내 표준 규정의 일부로
> 보입니다."

Two sentences. The user has just watched the agent "work hard" for
~12 seconds. The output looks like the agent gave up halfway.

**Why it happens**

Most hedge-output prompts are written defensively — "if you don't
find it, say so." That logic is correct, but the *length* and *shape*
signal is wrong. A two-sentence dismissal after rich activity reads
as laziness, even when the conclusion is correct.

There is also an asymmetry: a successful answer is naturally long
(it has content to render). A hedge has no content. So the default
generation produces a short hedge and a long success — which means
"hedge looks lazy" is built into the system unless the prompt fights
it.

**Fix — substantive 5-part out-of-corpus answer shape**

When the corpus does not contain the answer, the answer must match
the activity that produced it. Five parts, 5–8 sentences total — not
a wall of text:

1. **Clear conclusion** (1 sentence). State plainly. Avoid vague
   "may be in upper-tier regulations" — be direct. Conditional
   wording: if related docs ≥ 0.55 will be listed in part 3, soften
   the opening so it does not contradict the listing; otherwise keep
   it harsh.
2. **Scope of search** (1 sentence). Briefly name what was searched —
   SOP index, QMS index, wiki. The user should see that the corpus
   is bounded, not that the agent is incompetent.
3. **Closest internal documents** — only if at least one chunk has
   rerank ≥ 0.55 AND is genuinely on a related topic. List 1–3, each
   with one sentence on what they DO cover and why they are NOT the
   source the user asked for. If no chunk meets this bar, OMIT this
   part entirely. Do not pad with weak citations.
4. **Probable external source** (1–2 sentences). When the wording or
   framing points to an external regulation, name the most likely
   candidate based on distinctive phrasing in the user's text. Do
   not invent a specific article number, notification number, or
   revision year.
5. **Concrete next step** (1 sentence). Suggest the user check the
   named external source directly, OR re-ask with alternative
   keywords if they want to find an internal implementation of that
   external rule.

Never reply with "couldn't find an exact match" alone. Never
recommend "ask differently" without naming what was searched and
what the probable external source is. If you cannot identify a
probable external source (part 4), say so explicitly — do not guess
a regulation.

The shape applies to ANY out-of-corpus answer, not just verbatim
quotation lookups. The same template works for a query whose topic
isn't in the corpus, or a query that needs a doc that wasn't
indexed.

## How the three fixes compose

Each fix targets a different surface:

| Fix | Surface | Class |
|---|---|---|
| VERBATIM-CLAIM HONESTY | Agent's streamed `thought` | Prompt rule |
| Display floor | Reference card emission | Code (numeric, no semantics) |
| 5-part answer shape | Generation LLM output | Prompt rule |

The contradiction (1) is fixed at the agent's input boundary. The
misleading citation (2) is fixed at the SSE boundary between server
and frontend. The dismissal (3) is fixed at the generator's output.
They compose because they do not share state; each can land
independently and any subset improves the hedge surface.

What the user sees after all three: an agent that worked, found
related-but-not-matching documents, named what it searched, named the
probable external source, and pointed to a concrete next step. The
hedge becomes a usable answer rather than a refusal.

## What this isn't

- **It isn't a retrieval improvement.** The pasted regulatory passage
  genuinely is not in our corpus; no amount of better retrieval will
  find it. The fix is at the surface, not at the index.
- **It isn't a hallucination.** The hedge is correct. The bug is in
  how the correct hedge is presented.
- **It isn't a regex on the agent's output.** The display floor is
  numeric (`score >= 0.55`); no Korean string matching. The other
  two fixes are prompt rules where the LLM judges, not us.

## Diagnostic checklist

When a user reports any of the following, map directly to one of the
three fixes:

- "The agent said it found something then said nothing was found"
  → fix #1.
- "The cited document has nothing to do with my question"
  → fix #2.
- "The agent gave up too fast / felt lazy"
  → fix #3.

All three are about the gap between the activity the user watched
and the surface they read. Close the gap on each surface
independently.

## Where it fits with chapter 09

Chapter 09 covers escape *rules* — how the agent decides to stop
re-searching. This chapter covers what happens *after* the agent has
correctly decided to escape. The two are sequential: 09's rules tell
the agent "stop and call final_answer with a hedge"; 10's surface
patterns govern how that hedge is shown.

If you ship 09 without 10, the agent escapes correctly but the
escape *looks* lazy. If you ship 10 without 09, the surface is
polished but the agent still spins through dead ends. Both are needed
to make multi-turn dead ends feel like answers, not refusals.
