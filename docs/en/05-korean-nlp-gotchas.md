# Korean NLP gotchas for agentic RAG

Most agentic RAG cookbooks are written in English, for English. If your
users type in Korean, you will hit a specific set of failure modes that
never show up in the English-language demos. Each one has cost me days.

## 1. Particles eat your filters

Korean glues **grammatical particles** (조사) onto nouns. "고형제만 추려줘"
is **고형제 + 만** — `만` is a particle meaning "only". If your agent
passes `title_contains=["고형제만"]` to the search layer, it matches zero
records, because no document title contains the string `고형제만`.

Every string-valued filter the agent extracts from a query must be
**particle-stripped** before it hits the search layer:

| User phrase | Particle | What actually gets filtered |
|------------|----------|-----------------------------|
| `고형제만` | 만 (only) | `고형제` |
| `서울에서` | 에서 (from) | `서울` |
| `QC팀의` | 의 (of/possessive) | `QC팀` |
| `변경관리에 대한` | 에 대한 (regarding) | `변경관리` |
| `바이오 부서를` | 를 (obj marker) | `바이오 부서` |

**The failure mode is silent.** The search returns 0 results, the agent
assumes the data doesn't exist, and the user sees "해당 기록이 없습니다" —
for data that's sitting right there.

**Fix the schema, not the query.** Put this in the tool description, not
in a Python preprocessing step:

> "When extracting `title_contains`, strip Korean grammatical particles
> (만/의/에서/에/을/를/이/가/은/는). The particle is not part of the value."

Let the LLM do it. It's better at Korean morphology than your regex.

## 2. Category names don't appear in data

In pharma, **제형 (dosage-form)** categories like 고형제, 액제, 주사제 are
how humans talk. But the documents use **product-name tokens** — `정`,
`캡슐`, `환`, `과립`, `주`, `시럽`, `점안` — because those live in actual
product names (`A정`, `B캡슐`, `C주`).

The result: `title_contains=["고형제"]` returns 0 matches from a database
that has thousands of 고형제 records. The category label is never in the
title.

**The right handoff pattern:**

1. First attempt: respect the user's wording — try `title_contains=["고형제"]`.
2. If that returns 0 results: consult a wiki page for the category-to-token
   mapping (고형제 → 정/캡슐/환/과립/정제).
3. Retry with `title_contains_any=["정","캡슐","환","과립"]`.
4. In the final answer, **tell the user** you expanded the category to
   specific product forms — don't hide the substitution.

This is a wiki-augmented retrieval pattern. The mapping lives in a
markdown page the agent consults at inference time, not hardcoded.

## 3. Hedge-phrase regression

Korean LLMs — especially on QMS/SOP content — love these phrases:

- "직접적인 내용은 확인되지 않습니다" (no direct info)
- "관련된 명시적 언급은 없으나..." (no explicit mention, but...)
- "해당 SOP만으로는 파악이 어렵습니다" (can't tell from this SOP alone)
- "추가 확인이 필요합니다" (further verification needed)

They are sometimes correct. They are **often a hedge the model applies
reflexively** — even when the retrieved chunks contain the exact answer
at a specific section number. The user reads "직접적인 내용은 없습니다" and
concludes the system doesn't work.

**Fix direction (prompt, not code):**

- Explicitly forbid the phrase `"직접적인 내용은 없"` in the generation
  prompt unless the retrieved chunks are genuinely empty.
- Reframe the guidance: "If chunks contain partial information, quote
  the partial information and cite the section — do NOT hedge with
  '직접적인 내용은 없다' and walk away."
- Add a few-shot example where the correct answer cites section 5.1.4
  even though the chunk only addresses half the question.

## 4. Tokenizer variance breaks hybrid search

Hybrid search (dense + sparse) assumes the sparse tokenizer produces
stable tokens across index-time and query-time. Korean breaks this:

- Different BGE-M3 builds can tokenize `정제` as `정제` (one token) vs.
  `정` + `제` (two tokens) depending on tokenizer version.
- Morphological analyzers (Mecab, Kiwi, Khaiii) disagree on where to split.
- Normalization (NFC vs NFD) changes Unicode for Hangul syllables —
  visually identical strings can have different byte sequences.

**The symptom:** a corpus that ranked perfectly last week now drops the
same query to position 15. No code changed. A tokenizer patch shipped
silently.

**Defenses:**

- Normalize Hangul (`unicodedata.normalize("NFC", s)`) at **both** index
  and query time. Pick one form and lock it.
- Pin the sparse embedding model version. Do not use `:latest`.
- On any embedding rebuild, re-run a small golden-query suite and diff
  the top-10 against the previous baseline. Stop the rebuild if it
  diverges beyond a threshold.

## 5. Spacing is semantically loaded, sometimes

"고 형제" vs "고형제" — one is "high brother" (nonsense), one is
"solid-dosage form". A typo changes everything. Milvus exact-match
filters will happily miss the well-spelled documents because the user
typed a space.

Less obvious: `바이오QC` vs `바이오 QC` vs `바이오-QC` — all common,
none equivalent for string matching.

**Defenses:**

- For `title_contains`, index **both** spaced and unspaced variants of
  known department/team names.
- At query time, test the user's string against your synonym table
  (wiki!) before giving up. If "바이오QC" returns 0 and "바이오 QC"
  exists in synonyms, retry.
- Never build this logic with regex. Put the synonym table in a wiki
  page the LLM reads.

## 6. Homonyms collapse your stem

- `정` → could be 錠 (tablet), 正 (correct), 情 (feeling), or a name suffix.
- `주` → 주사제 (injectable), 週 (week), 株 (share), 주님 (lord).
- `일탈` → deviation (the QMS term) OR "going astray" (general Korean).

Context disambiguates — so **don't try to disambiguate with code**. The
LLM is excellent at this if you give it the domain context in the system
prompt.

## 7. English prompt → Korean output is usually better

Counterintuitive but real: many Korean LLMs (Qwen, Gemma lineages)
**follow English instructions more reliably** than Korean ones. Same
model, same task, same inputs — English system prompt + `output in
Korean` produces cleaner structure.

Why: the model's instruction-tuning data has more English instructional
patterns than Korean. It learned "follow a bulleted list" in English far
more thoroughly than in Korean.

**Pattern we use:**

- System prompt: English instructions + rules + few-shot examples.
- Explicit directive at the end: `"Always write the final answer in
  natural Korean (한국어로 답변)."`
- Observations from tools: keep in English where possible.

Your Korean-speaking users never see the English. They see clean Korean
output that followed the rules more reliably than a Korean-only prompt
would have produced.

## 8. Bracket-leak regression (model-specific)

Gemma-4 on Korean content loves to copy bracketed prompt annotations
**verbatim into the user-facing output**:

- You write `[NOTE: cite the page number]` in the generation prompt.
- Gemma produces: `"... 5.1.4항 [NOTE: cite the page number]에 따르면..."`.

The bracket content ends up in the rendered answer. Users see your
internal annotation.

**Defenses:**

- Do not use `[NOTE:...]`, `[HINT:...]`, `[IMPORTANT:...]` inside
  prompts for Gemma. Use inline imperatives instead ("Always cite the
  page number.").
- Add a post-gen regex that strips `\[NOTE:[^\]]+\]` patterns from the
  final answer (this is one of the few legitimate uses of regex — it's
  data hygiene, not semantic routing).
- Run a smoke test after any model change: look for `[` in outputs.

## Quick checklist before you ship

- [ ] Does every string filter your agent sets get **particle-stripped**
      by the prompt, not by Python?
- [ ] Do all Korean category labels have a **wiki-backed token fallback**?
- [ ] Is the generation prompt **explicitly banning** the hedge phrases
      your LLM abuses?
- [ ] Is Hangul **normalized (NFC)** at both index and query time?
- [ ] Is the sparse embedding model **version-pinned**?
- [ ] Are you running a **golden-query diff** after every embedding
      rebuild?
- [ ] Are department/team synonyms in a **wiki page**, not in
      `if/elif` branches?
- [ ] For Gemma specifically: no `[NOTE:...]` in prompts, and a
      bracket-stripping regex on output?
