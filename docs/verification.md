# Verify outcomes

An agent's report that its work is done and correct is a claim, made with the same confidence
whether it holds or not. So an outcome counts as verified only when something other than the
agent's own judgment checked it: a program that runs, or a reviewer that does not share the
author's view of the change. Checks are cheap to run with agents, so they run on every change, and
the same prompt can give different results, so a check on a prompt is run more than once.

## In my-claude

- A required CI check ([ci.yml](../.github/workflows/ci.yml)) runs lint, format, type, and test
  checks, and nothing merges until it passes.
- The "TDD and testing" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) put a failing test
  before every change and every bug fix.
- [test-review](../dot-claude/skills/test-review/SKILL.md) mutates the changed code to prove the
  tests can fail, on every PR that changes code.
- `/code-review`, bundled with Claude Code, reviews every PR before merge.
- [file-issue](../dot-claude/skills/file-issue/SKILL.md) files a failure only once a run has shown
  it.
- The cases in [evals/](../evals/) run the skills against real models and grade what they do.

## Known gaps

- *Unseen:* the code review runs in the session that wrote the change, with the same model, and
  that session triages its findings; the review never blocks a merge. Only CI and the mutation
  runs check a change independently of its author.
- *Unseen:* no case in `evals/` fixes how many runs it takes, so a pass rate is known only when
  someone reruns a case.
