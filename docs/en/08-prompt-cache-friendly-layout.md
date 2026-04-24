# Prompt-cache-friendly layout — moving one line to the bottom

> Prefix cache hits jumped from ~1% to ~99% by moving `Today's date:`
> from line 6 of the system template to the very end. Same model, same
> answer, much cheaper at scale.

vLLM (and most modern OSS inference engines) implement **automatic
prefix caching** — when two prompts share a token-prefix, the engine
reuses the KV-cache for that prefix and only runs prefill for the
divergent tail. This is free if you opt in (`--enable-prefix-caching`)
and your prompt layout is friendly to it.

The trap: **the cache fingerprint diverges at the FIRST dynamic token.**
One innocuous variable near the top of the prompt — today's date, the
user's name, a request ID — voids the cacheability of everything below.

## A real before/after

Production agent system prompt (Korean pharma RAG, ~22K chars assembled):

**Before (typical layout):**
```
Line 1: You are a pharmaceutical {domain_label} search coordinator.
Line 2: Your job is to find the right data — NOT to analyze ...
Line 3: A separate generation model will receive ALL your search results...
Line 4: <blank>
Line 5: <blank>
Line 6: Today's date: 2026-04-24                  ← DYNAMIC, breaks cache
Line 7: <blank>
Line 8: ## Recipe
Line 9: <recipe_yaml — ~2,700 tokens of static action schemas>
...
Line 32+: ## Rules (~5,000 tokens of static instructions)
Line 120+: ## final_answer format ...
```

For two queries on the same recipe, the prompt is byte-identical for
~250 chars (lines 1–5), then diverges at line 6 where today's date
appears. vLLM's prefix cache matches up to the first divergence, so
~99% of the prompt is **re-prefilled** every call.

**After (one-line move):**
```
Line 1: You are a pharmaceutical {domain_label} search coordinator.
Line 2: Your job is to find the right data — NOT to analyze ...
Line 3: A separate generation model will receive ALL your search results...
Line 4: <blank>
Line 5: ## Recipe
Line 6: <recipe_yaml — ~2,700 tokens of static action schemas>
...
Line 100+: ## Rules ...
Line 220+: ## Output Format ...
Line 230: ## Runtime Context
Line 231: Today's date: 2026-04-24                ← DYNAMIC, now at the tail
```

For two queries on the same recipe, the first ~22K chars are now
byte-identical. Prefix cache hits cover ~99% of the prompt. Same model
sees the same instructions, in a slightly different order; final
answers are unchanged. Date-relative queries ("최근 한달간") still
resolve correctly because the date is still in context — just at the
end instead of the start.

## What "static" actually means

For the cache to hit, you don't need everything to be literally
identical across all queries. You need a **token-prefix that is
identical for the queries you want to share a cache slot.** That
boundary depends on which queries cluster together in your traffic:

- **All queries on the same recipe + same date** → cache covers
  everything from line 1 down to (but not including) the date line.
  This is the normal case — recipes are stable, date changes once a
  day.
- **All queries period (regardless of recipe)** → cache covers only
  the universal preamble (lines 1–4 in the example). Per-recipe
  content already diverges by line 5.
- **All queries by the same user / role / domain** → cache covers up
  to wherever you interpolate user-specific text.

The general principle: **arrange the prompt so the variables that
change most often are last, and the variables shared by the largest
cluster of queries are first.**

## A layout you can copy

```
[A. UNIVERSAL — identical for every call]
   Role description (no domain interpolation)
   Output format example
   Generic guardrails (be honest, cite sources, ...)

[B. PER-RECIPE — identical across all queries on this recipe]
   Domain label
   Recipe schema (action params, allowed tools)
   Rules
   Final-answer format

[C. PER-CALL — re-rendered every request]
   ## Runtime Context
   Today's date: {today}
   ## Previous Context (if multi-turn)
   {SESSION_STATE block}
   {Conversation history if not handled separately}
```

Block A is shared across every cache slot. Block B is shared across
queries on the same recipe. Block C is fresh every call but is small.
Three matched cache strata, in priority order, with the most-shared
content first.

## Why this is undersold

Most agent codebases were written before prefix caching shipped (or by
people who weren't watching `--enable-prefix-caching` flags), so the
prompt layout reflects historical readability — date and user info at
the top because they "set the scene." That made sense when every
prompt was prefilled fresh. Today it's a quiet ~10-100× cost
multiplier on inference for any agent that reuses a recipe across
queries (which is almost all of them).

Two-minute change, no change in agent behavior, no change in answer
quality, no rebuild of the prompt content. The kind of optimization
that gets skipped because it sounds too small to matter and ends up
being one of the largest line-item wins on the inference bill.

## Verifying the win

You can confirm both halves of the change with three short steps:

1. **Confirm the engine has it on.**
   `journalctl -u vllm | grep -i prefix-caching` or check the systemd
   unit for `--enable-prefix-caching`. (For SGLang it's usually on by
   default.) If it's not on, the layout change does nothing — turn the
   flag on first.

2. **Confirm the prompt is actually static.**
   Render the system prompt with two distinct user queries (same recipe)
   and `diff` them. Everything except the runtime-context tail should
   be byte-identical. If something else differs (a UUID, a random
   model_id suffix, a millisecond timestamp), find it and move it.

3. **Confirm the cache is hitting.**
   `curl http://<vllm-host>:<port>/metrics | grep prefix_cache` —
   most engines expose a hit rate metric. Or grep the engine's stdout:
   vLLM logs `Prefix cache hit rate: 51.6%` style lines. The absolute
   number depends on your traffic mix; what you want to see is that
   the rate goes UP after the layout change for a workload that
   repeats recipes.

## What this doesn't fix

Prefix caching reuses **prefill** compute, not **decode** compute.
If your output is long (a 4K-token final answer), the decode cost
dominates and the prefill saving is a smaller fraction of the
end-to-end latency. The win is biggest when:

- You have many short outputs per session (agent ReAct steps emitting
  tool-call JSON are perfect for this — the JSON is short, the prompt
  is long, prefill dominates).
- Many users share the same recipe (multi-tenant SaaS where every user
  hits the same product).
- Your context is large relative to the output (any retrieval-augmented
  agent).

Decode-bound workloads benefit less; speculative decoding is the
relevant optimization there.

## And: tie cache invalidation to prompt content

A subtle dependency falls out of this layout. Once the cache is hitting
~99% on a recipe, the model is effectively *frozen* on whatever prompt
was loaded at process start. If you edit a rule and forget to restart,
in-flight queries will get the old prompt's KV-cache for the prefix
even after your YAML hits disk.

A small mitigation: hash your prompt + recipe directory at process
start and log the fingerprint:

```python
def _compute_prompt_fingerprint() -> str:
    h = hashlib.md5()
    h.update(Path("config/prompts/system_template.yaml").read_bytes())
    for f in sorted(Path("recipes").rglob("*.yaml")):
        h.update(f.read_bytes())
    return h.hexdigest()[:8]

PROMPT_FINGERPRINT = _compute_prompt_fingerprint()
log.info("Prompt fingerprint: %s", PROMPT_FINGERPRINT)
```

If you also have an answer-level cache (like an agent-loop result
cache), include the fingerprint in those keys so cached answers
auto-invalidate when the prompt changes. The vLLM prefix cache itself
clears on engine restart, which any prompt change requires anyway —
but the fingerprint makes the dependency explicit and audit-able.
