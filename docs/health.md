# Keep the work healthy

Terms in *italics* are defined in [the index](README.md).

People absorb a team's standards over time; an agent with *thin or stale context* knows only those
written where it reads them. So the standards are written once, reach every agent through *one
rulebook*, and are checked by a program where one can judge them and by a review where only
judgment can.

## In my-claude

- [CLAUDE.md](../dot-claude/CLAUDE.md) holds the code, readability, prose, and docs standards that
  hold in every repo.
- The [check_prose](../dot-claude/hooks/check_prose.py) hook checks on every edit the prose
  conventions a program can.
- `/simplify`, bundled with Claude Code, cleans up each change with code outside tests before it
  is committed.
- [docs-review](../dot-claude/skills/docs-review/SKILL.md),
  [dead-code-review](../dot-claude/skills/dead-code-review/SKILL.md),
  [naming-review](../dot-claude/skills/naming-review/SKILL.md), and
  [hindsight-review](../dot-claude/skills/hindsight-review/SKILL.md) find the debris fast work
  leaves behind.
- [install.sh](../install.sh) puts the same rulebook on every machine.

## Known gaps

- *Unseen:* those four reviews run only when the developer asks, so debris builds up between runs.
