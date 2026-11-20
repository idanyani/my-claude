# Verify outcomes

Terms in *italics* are defined in [the index](README.md).

An agent's report that its work is done and correct is a claim, made with the same confidence
whether it holds or not: output can be *plausible but wrong*. So an outcome counts as verified
only when something other than the agent's own judgment checked it: a program that runs, or a
reviewer that does not share the author's view of the change. *Cheap work* makes checks affordable
on every change they apply to, and *non-determinism* means a check on a prompt is run more than
once.

## In my-claude

- A required CI check ([ci.yml](../.github/workflows/ci.yml)) must pass before anything merges.
- The "TDD and testing" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) set how code changes
  are tested.
- [test-review](../dot-claude/skills/test-review/SKILL.md) proves the tests of each PR can fail.
- `/code-review`, bundled with Claude Code, reviews every PR before merge.
- [file-issue](../dot-claude/skills/file-issue/SKILL.md) files a failure only once a run has shown
  it.
- The cases in [evals/](../evals/) check, against real models, which requests reach which skill,
  and for some skills what it writes.

## Known gaps

- *Unseen:* the code review runs in the session that wrote the change, with the same model, and
  that session triages its findings; the review never blocks a merge. Only CI and the tests'
  mutation runs check a change independently of its author.
- *Unseen:* the evals run only by hand, and no case fixes how many runs it takes, so a skill's pass
  rate is known only when someone reruns its cases.
