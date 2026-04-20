# pharma-agent

Production lessons from building an agentic RAG system for a Korean pharmaceutical
company over three months. Not a framework. A **field guide** — the non-obvious
failure modes, the disciplines that prevented them, and the prompts/patterns that
actually shipped.

## Why this exists

Most agentic RAG writeups are toy demos or generic LangChain tutorials. (Which is great, And I love lanchain framework.) 
Production systems — especially in **regulated industries** with **multi-turn Korean queries**
— break in ways that don't show up in the toy version:

- The agent's thinking panel shows a better answer than the final output.
- Followup turns broaden into unrelated data instead of filtering prior results.
- The verifier flags spurious mismatches because it can't see prior-turn context.
- "Quick fix" if-else chains silently degrade routing after every LLM upgrade.

We hit all of these in production. The fixes are never what you'd guess on the
first read. This repo documents them.

## Scope

- **In**: prompt patterns, failure modes, session-state design, verifier design,
  Korean NLP gotchas, regulated-industry citation discipline.
- **Out**: a full framework. We use FastAPI + Milvus + vLLM; your stack can
  differ. The patterns are framework-agnostic.

## Layout

Docs are published in English and Korean (한국어). Both versions are maintained
side by side — pick whichever you prefer.

| Topic | EN | KO | Status |
|-------|----|----|--------|
| Prompt-first debugging — code is a last resort, not a first reach | [`docs/en/01-...`](docs/en/01-prompt-first-debugging.md) | [`docs/ko/01-...`](docs/ko/01-prompt-first-debugging.md) | ✅ |
| Bug patterns — failure modes we hit repeatedly + fix direction | [`docs/en/02-...`](docs/en/02-bug-patterns.md) | [`docs/ko/02-...`](docs/ko/02-bug-patterns.md) | ✅ |
| Session state design — what to persist between turns | [`docs/en/03-...`](docs/en/03-session-state-design.md) | [`docs/ko/03-...`](docs/ko/03-session-state-design.md) | ✅ |
| Verifier cross-turn context — why post-gen verifiers false-positive on followups | [`docs/en/04-...`](docs/en/04-verifier-cross-turn.md) | [`docs/ko/04-...`](docs/ko/04-verifier-cross-turn.md) | 🟡 draft |
| Korean NLP gotchas — particles, 제형 classification, hedge-phrase regression, Hangul normalization, bracket-leak | [`docs/en/05-...`](docs/en/05-korean-nlp-gotchas.md) | [`docs/ko/05-...`](docs/ko/05-korean-nlp-gotchas.md) | 🟡 draft |
| Pharma-specific patterns — QMS/SOP/CAPA, 변경관리 citation, dosage-form fallback | [`docs/en/06-...`](docs/en/06-pharma-specific.md) | [`docs/ko/06-...`](docs/ko/06-pharma-specific.md) | 🟡 draft |

Other folders:

- `prompts/` — example system prompts, recipes, verifier templates. _(TBD)_
- `examples/` — minimal reference implementations, illustrative not production-grade. _(TBD)_
- `skills/` — short field-guide snippets for Claude Code / Codex / Copilot CLI, distilled from these docs. Currently: [`korean-multiturn-rag`](skills/korean-multiturn-rag/) — helps you build a multi-turn Korean chatbot. Honest caveat: on frontier models like Haiku 4.5, most of these patterns are already handled natively — the skill's measurable delta is small. Install via symlink into `~/.claude/skills/` — see [`skills/README.md`](skills/README.md).

## Who this is for

- Engineers building production agentic RAG, especially for:
  - Regulated industries (pharma, finance, legal) where wrong answers have consequences.
  - Multi-turn conversational workflows where followups must reason over prior data.
  - Non-English languages where tokenizer/particle behavior changes search results.
- Anyone debugging an agent whose thinking log looks smarter than its final answer.

## Install the skill (for Claude Code)

If you use Claude Code, Codex CLI, or any skill-aware harness, the
`korean-multiturn-rag` skill can be auto-loaded whenever you work on a
Korean multi-turn chatbot.

```bash
# one-time install — symlink the repo into your user skills directory
git clone https://github.com/papago2355/pharma-agent.git
cd pharma-agent
ln -s "$PWD/skills/korean-multiturn-rag" ~/.claude/skills/korean-multiturn-rag

# verify the harness sees it
ls -la ~/.claude/skills/korean-multiturn-rag/SKILL.md
```

After symlinking, restart your Claude Code session. The skill's
`description` triggers on Korean multi-turn RAG topics ("X만", "그럼 X는",
"followup broadens", etc.) and Claude Code auto-loads it.

**For Codex / Copilot CLI / other harnesses**: same symlink pattern into
that harness's skill directory (check its docs for the path).

**No harness?** Just read [`skills/korean-multiturn-rag/SKILL.md`](skills/korean-multiturn-rag/SKILL.md)
as a field-guide checklist and apply the patterns by hand into your own
system prompts.

**Run the benchmarks to see what the skill measurably changes** (and
doesn't — we're honest about it):

```bash
cd skills/korean-multiturn-rag/benchmarks/behavioral
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...
pytest -v
```

## Status

Early. The docs are being ported from production notes. PRs welcome with your own
failure modes, especially if you can pair a symptom with the specific fix that
worked.

## License

MIT. Take whatever's useful.