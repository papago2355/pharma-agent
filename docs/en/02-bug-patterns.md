# Bug patterns in production agentic RAG

Each of these cost us days. The symptom is often misleading — the real fix
is rarely where you first look.

## 1. Thinking log > final answer

**Symptom**: the agent's visible reasoning contains the right information,
but the final answer is hedged, shorter, or wrong.

**Root cause**: the generation LLM runs as a separate call and doesn't see
everything the agent saw. If the agent's reasoning referenced data that
lives in a place the generator can't read (session state, prior-turn
observations, filter-tool context pasted into the user query), the
generator gets a "no data, refuse" directive alongside records it can
partially see — and splits the difference.

**Fix direction**: ensure the generator's context is a *superset* of the
agent's context. Either inject prior records as a synthetic step-0
observation, or pass prior-turn context explicitly into the generation
prompt.

## 2. Followup broadens instead of filtering

**Symptom**: turn 1 returns 11 targeted records. Turn 2 ("X만 추려줘")
returns 5529 generic records. The answer happens to cite correct rows
from turn 1's memory, but the references panel shows unrelated results.

**Root cause**: the agent's followup template doesn't expose prior-turn
raw records. Re-searching loses the prior topic filter. The agent has no
mechanism to say "I want to filter what I already have."

**Fix direction**: persist top-N prior records in session state. Surface
them in the followup's system prompt as a "[PRIOR RECORDS — FILTERABLE]"
block. Update the prompt rule to allow filtering-in-thought on subset
requests.

## 3. Verifier false-positives on cross-turn reasoning

**Symptom**: answer is correct but the verifier flags it as fabricated.
The verifier points to numbers in the answer that it can't find in the
current-turn context.

**Root cause**: the verifier only receives this-turn generation context.
When the answer legitimately reasons over prior-turn data, every such
claim looks like a hallucination to the verifier.

**Fix direction**: pass prior-turn context into the verifier's prompt as
a separate, explicitly-labeled section. Update the verifier's rules to
treat prior-turn evidence as valid.

## 4. Hedged tone despite high-score retrievals

**Symptom**: references panel shows highly relevant docs (scores 0.8+),
but the answer says "관련 정보를 찾을 수 없습니다" or hedges with "직접적인
내용은 없으나..."

**Root cause**: usually not a retrieval problem — it's a prompt problem.
The generation prompt has conservative language ("only cite what is in
context", "never fabricate") that the LLM over-applies. Chunks contain
partial info → LLM refuses rather than quoting the partial info.

**Fix direction**: rewrite the generation prompt to distinguish "no
information" from "partial information". Explicitly permit citing page
numbers, section numbers, and partial quotes. Forbid the phrase "only
chunks" in hedges.

## 5. Hardcoded routing rotting after model upgrades

**Symptom**: routing code full of `if "keyword" in query:` branches.
Works on one model. Silently regresses when the model is swapped.

**Root cause**: every hardcoded branch encodes assumptions about how the
LLM tokenizes and responds. A new model breaks those assumptions
invisibly — no test fails, but specific queries drift.

**Fix direction**: replace routing branches with tool schemas and recipe
descriptions the LLM reads at inference time. If a branch must exist,
make it a **tool parameter** the LLM chooses, not a code-level check.

## 6. Step-number mismatch in typed sections

**Symptom**: agent produces a typed-section `final_answer` referencing
steps that don't contain records. Generator renders an empty table.

**Root cause**: the agent picked a step number heuristically (e.g.,
"step 2 was the successful search") but that step was a retry with 0
results. The actual records are in step 1.

**Fix direction**: (a) fallback in the generator — when a referenced
step has 0 records, use all non-final steps. (b) let the agent omit
`steps[]` entirely (default to all).

## 7. Context overflow from over-retrieving

**Symptom**: answer quality degrades sharply when retrieved chunks
exceed a certain count. Output becomes generic despite specific docs
being retrieved.

**Root cause**: generation context approached the model's limit. LLM
silently truncated chunks or lost attention on key details.

**Fix direction**: log total token count into the generation prompt.
Cap chunks by *relevance score*, not count. Prefer fewer high-quality
chunks over many marginal ones.

## 8. SSE streaming cuts off mid-response

**Symptom**: users see a partial answer that ends abruptly. No error
in logs. Retrying the same query produces a complete answer.

**Root cause**: downstream client read timeout, or the LLM hit a
context limit mid-stream. Sometimes a tool result embedded in the
prompt exceeds the model's input budget.

**Fix direction**: (a) reduce the prompt size before streaming starts.
(b) add server-side timeout headers. (c) instrument the SSE stream
with a `done` event the client can wait for — if absent, show a
"connection lost, retry?" prompt rather than silently displaying
partial output.
