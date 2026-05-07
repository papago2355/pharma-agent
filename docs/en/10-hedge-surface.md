# Hedge cases — making "not found" look honest, not lazy

The moment an agent gives a hedge — its defensive "I don't have a
confident answer" reply — is the moment the user is most likely to
lose trust in the entire conversation. The user has just spent ten or
twelve seconds watching the agent issue search calls, narrate its
`thought` process, and pull documents. Then the reply comes back as
"couldn't find an exact match." If the trail looked rich and the
answer reads thin, the user does not interpret it as honesty. They
interpret it as **the agent gave up halfway through.**

This chapter covers three independent failure modes that all surface
at the hedge boundary. Each produces a different "looks lazy" signal,
and each has to be fixed at a different surface (the agent's
streamed thoughts, the SSE event the frontend reads, or the
generation LLM's final output).

1. **A contradiction between the agent's `thought` and its final
   answer** — the streamed thinking trail says "found a matching
   document," and the final answer says "nothing was found." The
   user reads both.
2. **A misleading citation card next to the hedge** — the answer
   says "not found," and the reference card next to it shows a
   document with relevance score 0.50 that has nothing to do with
   the question.
3. **A one-sentence dismissal** — after four search steps and a long
   thinking trail, the final answer is two sentences. The output is
   wildly out of proportion with the visible activity that produced
   it.

None of the three fixes is large on its own. But all three have to
land for the hedge surface to feel proportionate to the work that
preceded it.

## 1. The verbatim-claim contradiction

**Symptom**

A user pastes a verbatim regulatory passage and asks, "where does
this come from?" The agent runs:

```
Step 1 (search): "사용자가 입력한 문구가 포함된 문서를 검색한 결과,
  '<related-procedure-A>.pdf'와 '<related-procedure-B>.pdf' 두 건의
  관련 문서가 확인되었습니다."

Step 2 (document_fetch): "검색 및 문서 추출 결과, 사용자가 입력한
  문구와 정확히 일치하는 내용을 포함한 문서를 찾았습니다. ..."

Final answer: "사용자께서 인용하신 문구는 사내 색인 어디에도
  등재되어 있지 않습니다."
```

The user reads step 2 ("정확히 일치를 찾았다" — exact match found)
and the final answer ("색인에 없다" — not in the corpus) on the same
screen. It is a direct contradiction. Even when the final answer is
factually correct, the user's trust is already gone by the time they
get to it.

**Why it happens**

The agent's per-step `thought` is generated from the *metadata* of
search results — file_name, score, doc_id — not from the *text* of
the chunks themselves. Two related SOPs ranking high on dense
similarity is enough for the agent to write "I found an exact match."
Then the generation LLM, which actually reads the chunk text, sees
no verbatim overlap and (correctly) hedges.

Inside the same turn, the agent and the generation LLM are looking
at different evidence and reaching different conclusions. The user
sees both outputs side by side, sees they disagree, and concludes
that one of them is lying.

The deeper bug is "topical relevance ≠ verbatim presence." Dense
retrieval is excellent at finding documents *about the same subject*,
but it is not phrase search. The agent's intermediate thought
confuses the two.

**Fix — the VERBATIM-CLAIM HONESTY rule**

Add a system-prompt rule that gates the content of the agent's
`thought`.

> Do NOT write "정확히 일치하는 내용을 포함한 문서를 찾았습니다" or
> "해당 문구는 …에 포함되어 있습니다" in your `thought` unless a
> substantive substring of the user's quote (≥ 10 Korean characters,
> or one full clause) literally appears in the retrieved chunk text.
>
> When the chunks are topically related but the verbatim text is
> not present, say that explicitly: "주제가 일치하는 사내 문서는
> 확인되었으나, 인용하신 문구가 청크 내에 직접적으로 포함되어
> 있지는 않습니다."
>
> The rule applies in both directions. Do not over-claim a match,
> and do not under-claim ("nothing found") when topical chunks DID
> come back.

Why it works: the agent now has explicit guidance to distinguish
*topical relevance* from *verbatim presence*, and the `thought`
streaming to the user is grounded in the same evidence as the final
answer.

This is a prompt rule, not a regex muzzle on agent output. Whether
the user's substring is present in a chunk is something the LLM
should read and judge — not something we hard-code from the outside.

## 2. The misleading citation card

**Symptom**

The answer says "이 정확한 문구는 사내에서 확인되지 않습니다" — the
exact phrase is not in our corpus. The reference card sitting next
to that answer shows `<unrelated-topic>.pdf` at score 0.5038, a
document on a completely different subject from what the user asked
about.

The user does not bother to read the relevance score number. They
look at the doc card next to the hedge and conclude one of two
things: "the agent contradicted itself" or "this is the source and
the agent failed to read it." Both readings are wrong, but both are
the surface's fault.

**Why it happens**

Search retrieval has a relevance threshold (in production, often
something like rerank ≥ 0.40, calibrated as "borderline relevant").
The reference list shown in the UI typically reuses that same list.
But "borderline relevant" at the retrieval stage is "definitely not
the source" at the presentation stage. A document the user sees with
their own eyes is implying a relationship the document does not
actually have.

**Fix — separate the display floor from the retrieval floor**

Apply a numeric score floor *at the user-facing emission boundary*
(empirically ≥ 0.55 for BGE-reranker output). This is pure data
validation, not a semantic decision — there is no Korean string
matching involved. The full reference list is still recorded on the
server for forensics; only the UI sees the filtered version.

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
floor for the LLM, which has to read weak matches and reason about
them. The display threshold (0.55, "worth showing the user") is the
right floor for the citation card. Same data, different consumers,
different floors.

This is the only fix in the chapter that needs no prompt rule —
numeric, deterministic, no surprising side-effects. If you take only
one thing from this chapter, take this one. It is the cheapest
improvement to the hedge surface in the entire guide.

## 3. The one-sentence dismissal

**Symptom**

After four search steps, document_fetch calls, and a long thinking
trail, the final answer is:

> "검색된 사내 규정 내에 해당 문구와 정확히 일치하는 내용은
> 발견되지 않았습니다. 외부 규제 가이드라인 또는 사내 상위 규정의
> 일부로 보입니다."

Two sentences. The user has just watched ~12 seconds of the agent
"working hard." The output reads as if the agent ran out of effort
and gave up.

**Why it happens**

Most hedge-output prompts are written defensively — "if you can't
find it, say so honestly." That is correct logically. But the
*length* and *shape* signals are wrong. After a rich exploration
trail, a two-sentence dismissal feels lazy regardless of whether
the conclusion is correct.

There is also an asymmetry. A successful answer naturally runs long,
because there is content to render. A hedge has no content to
render. So with default generation settings, success comes back
long and hedge comes back short. In other words, "the hedge looks
lazy" is built into the system unless the prompt actively fights it.

**Fix — a substantive five-part out-of-corpus answer shape**

When the corpus does not contain the answer, the answer should be
shaped to match the work that produced it. Five parts, 5–8
sentences total — long enough to feel proportionate, short enough
that it does not become a wall of text.

1. **Clear conclusion** (1 sentence). State the result plainly.
   Avoid vague hedges like "may be in upper-tier regulations." A
   conditional opening is fine — if part 3 will list documents at
   ≥ 0.55, soften the opening so it does not contradict the listing
   that follows; otherwise, keep it firm.
2. **Scope of search** (1 sentence). Briefly name what was actually
   searched — SOP index, QMS index, internal wiki. The user should
   come away thinking "the agent's reach is bounded," not "the
   agent is incompetent."
3. **Closest internal documents** (conditional). Only if at least
   one chunk has rerank ≥ 0.55 AND is genuinely on a related topic.
   List 1–3 documents, each with one sentence on what the document
   *does* cover and why it is *not* the source the user asked for.
   If no chunk meets this bar, OMIT this part entirely. Do not pad
   with weak citations to fill space.
4. **Probable external source** (1–2 sentences). When the wording
   or framing of the user's question points to an external
   regulation, name the most likely candidate based on the
   distinctive phrasing of the user's text. Do not invent a
   specific article number, notification number, or revision year.
5. **Concrete next step** (1 sentence). Suggest the user check the
   probable external source directly, OR — if they want to find an
   internal implementation of that external rule — suggest specific
   alternative keywords they can re-ask with.

Never close with "couldn't find an exact match" alone. Never say
"please ask differently" without first naming what you searched and
what you think the external source is. If you genuinely cannot
identify a probable external source (part 4), say so explicitly —
do not guess a regulation.

This shape applies to *any* out-of-corpus answer, not just verbatim
quotation lookups. The same template works for queries whose topic
is not in the corpus at all, and for queries that need a document
that was never indexed.

## How the three fixes compose

Each fix targets a different surface.

| Fix | Surface | Type |
| :--- | :--- | :--- |
| **VERBATIM-CLAIM HONESTY** | The agent's streamed `thought` | Prompt rule |
| **Display-floor separation** | Reference card emission | Code (numeric, no semantics) |
| **Five-part answer shape** | Generation LLM output | Prompt rule |

The contradiction (1) is fixed at the agent's input boundary. The
misleading citation (2) is fixed at the SSE boundary between server
and frontend. The dismissal (3) is fixed at the generator's output.
Because the three fixes do not share state, they compose cleanly —
each one can land independently, and any subset of them improves
the hedge surface.

After all three are in place, here is the agent the user
experiences: it searched hard, found related-but-not-matching
documents, was transparent about where it looked, named the
probable external source, and gave a concrete suggestion for what
to do next.

The hedge stops being a refusal and starts being a useful answer.

## Things to watch out for

*   **This is not a retrieval-quality problem.** If the user's text
    genuinely is not in the corpus, no amount of better retrieval
    will produce it. The fixes in this chapter live on "how the
    answer is presented," not on "how the index ranks documents."
*   **The hedge itself is not a hallucination.** The conclusion
    "we don't have this" is correct. The bug is purely in *how that
    correct conclusion is shown to the user.* Keep this distinction
    in mind when triaging user-submitted bug reports.
*   **Be careful with regex on agent output.** The display floor
    (`score >= 0.55`) is a numeric check with no Korean string
    matching, which is why it is safe. Trying to control every
    edge case with regex on agent output is a different proposition
    and almost always introduces its own bugs.

## Diagnostic checklist

When a user submits a complaint, you can usually map it 1:1 onto
one of the three fixes.

*   "The agent first said it found something, then said it didn't"
    → **fix #1.**
*   "The agent said it didn't find anything, but the cited document
    has nothing to do with my question"
    → **fix #2.**
*   "The agent gave up too fast / it feels like it didn't really
    try"
    → **fix #3.**

All three complaints are about the gap between **the activity the
user watched** and **the output the user ended up reading.** That
gap has to be closed at each surface independently.

## Relationship to chapter 09

Chapter 09 covered the *escape rules* — the signals an agent reads
to decide it should stop re-searching. This chapter covers what
happens *immediately after* the agent has correctly decided to
escape.

The two chapters are sequential. Chapter 09's rules tell the agent
"stop searching, call final_answer with a hedge." Chapter 10's
surface patterns govern what that hedge looks like on the user's
screen.

Ship 09 without 10 and the agent escapes correctly from infinite
loops, but the escape *looks lazy*. Ship 10 without 09 and the
surface is polished, but the agent is still spinning through dead
ends in a corpus that doesn't contain the answer.

To make a dead-end conversation feel like a useful answer rather
than a refusal, you need both chapters working together.
