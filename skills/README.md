# Skills

Distributable Claude Code / Codex / Copilot CLI skills extracted from
the pharma_agent field guide. Each skill is a focused, testable playbook
for one class of problems the docs describe.

## Available skills

| Skill | What it is | Trigger |
|-------|------------|---------|
| [`korean-multiturn-rag`](korean-multiturn-rag/) | Short field-guide snippets for engineers building a Korean multi-turn chatbot — session state design, subset-filter followups, particle stripping, verifier cross-turn context, hedge-phrase regression, LLM-over-regex routing, persistent-filter disambiguation. Reference material for the builder, not an inference-time magic wand. See [benchmarks/](korean-multiturn-rag/benchmarks/) for what the skill does and doesn't measurably change. | Korean conversational agents, multi-turn RAG, followups like "X만" / "그럼 X는" / "더 보여줘". |

Planned splits (not yet extracted from the docs): `regulated-rag-discipline`
(SOP three-field citation, filter-first QMS search, three answer shapes,
audit evidence trail) and `agent-prompt-debugging` (thinking-log mismatch,
hardcoded routing rot, step-number mismatch, hedged-tone triage).

## Install

Pick one per skill.

### Option 1 — symlink into your user skills dir

```bash
# from the pharma_agent repo root
ln -s "$PWD/skills/korean-multiturn-rag" ~/.claude/skills/korean-multiturn-rag
```

The Claude Code harness auto-discovers skills in `~/.claude/skills/` on
session start. Restart the session to pick it up.

### Option 2 — copy

```bash
cp -r skills/korean-multiturn-rag ~/.claude/skills/
```

### Option 3 — read as a field guide

If you are not on a skill-aware harness, `SKILL.md` stands on its own as
a markdown checklist. Apply the patterns by hand into your system prompts,
verifier prompts, and agent rules.

## Evaluate

Each skill ships with its own benchmark suite demonstrating the behaviors
the skill is claimed to improve. See `<skill>/benchmarks/README.md` for
how to run them. The behavioral suite is the honest one — it measures
agent tool-call behavior in a multi-turn loop, not just recall of skill
bullets.

## Contributing

A new skill should:
- Come with a RED/GREEN baseline showing the frontier model actually
  fails the target patterns without the skill, and passes with it.
- Include at least one behavioral scenario (live conversation with mock
  tools, graded on tool calls + final text).
- Stay domain-generic at the skill level; keep domain-specific details
  to scenario files.
