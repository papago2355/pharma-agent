# Prompt-first debugging

> When an agent misbehaves, your first hypothesis should be **"the prompt or
> tool schema is missing information"** — not **"the code has a bug."**

Most teams reach for code first. An agent picks the wrong tool → they add an
`if query.contains("X")` branch. Query returns too many rows → they add a
post-filter. Agent hedges on a specific answer → they add fallback templates.

Each patch scaffolds the LLM's behavior. Over enough months, your "agent" is
no longer agentic — it's a hardcoded state machine with an LLM glued on top.
When the next model upgrade ships, every scaffold becomes noise.

## The order

1. **Is a tool param missing?**
   Could a new parameter to an existing action let the agent express what
   the user is asking? A `title_contains` filter beats a hardcoded
   `if "고형제" in query:` branch.

2. **Is the system/recipe prompt missing an instruction?**
   Does the agent know the case exists? One sentence + one few-shot
   example almost always beats 30 lines of validation code.

3. **Is information missing from the observation the agent sees?**
   Surface counts, distributions, schema hints, or prior-turn context in
   the observation summary — not as hidden state the agent can't read.

4. **Only after 1–3 are exhausted**: write code. Even then, prefer a new
   small parameter over a fixed if/else in an existing function.

## The "is this really an LLM limitation?" test

Before writing code, answer all three:

1. **Reproducibility**: with a better prompt or one extra parameter, does
   the *same* model get this case right? If yes — it's a prompt gap.
2. **Generality**: does my proposed code patch help one case, or cover a
   real class of inputs? Single-case patches are almost always prompt
   issues in disguise.
3. **Reversibility**: would the patch survive a model upgrade or a recipe
   refactor? Hardcoded routing tables rot the moment the agent shifts.

If you can't answer "yes / yes / yes", the fix belongs in the prompt or
the tool schema, not in your service code.

## Symptoms that mean "go back to the prompt"

| Symptom | Fix layer |
|---------|-----------|
| "The agent doesn't know about X" | system prompt |
| "The agent passes the wrong field" | tool schema description |
| "The agent picks the wrong tool" | action description / recipe rule |
| "The agent miscounts" | expose the count in the observation summary |
| "The agent ignores prior context" | pass it through observation metadata |
| "The user said X but the agent searched Y" | add a few-shot example |

## Symptoms that genuinely warrant code

- A token-context overflow — a real engineering constraint.
- A streaming protocol contract the frontend depends on.
- A hallucination the verifier catches with no prompt fix possible.
- A schema mismatch where the data field literally doesn't exist.
- A budget enforcement that protects against runaway loops.

If your symptom isn't on this list, it belongs on the first one.

## The trap of "it's just one if-statement"

Every hardcoded branch looks harmless in isolation. The trap is cumulative.
After 30 of them, your routing is opaque, your tests are fragile, and your
next model upgrade has to re-prove every branch.

This is especially true for non-English languages. Korean morphology,
particle attachment, and spacing variations make regex/keyword routing
inherently unreliable. Every `if "X" in query:` you add is a time bomb.

## Exception: pure data validation

The rule applies to **semantic decisions** — intent detection, content
classification, relevance judgment. Pure data validation (checking a field
is non-empty, parsing a known wire format, validating a date) is fine in
code. The line: if you're using a string check to *classify user intent*,
that's a pattern the LLM should handle. If you're checking that a JSON
field is present before dereferencing, that's data hygiene.
