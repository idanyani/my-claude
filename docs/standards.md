# Keep the work healthy

Fast agent-driven work leaves debris behind: dead code, stale docs, names that stopped fitting,
designs a newer tool replaced. People absorb a team's standards over time; an agent knows only
those written where it reads them. So the standards are written once, reach every agent through
one rulebook, and are checked by a program where one can judge them and by a review where only
judgment can.

## In my-claude

- [CLAUDE.md](../dot-claude/CLAUDE.md) holds the standards that hold in every repo: "Less is
  more", "Small and neat code", "Readability", "Prose and docs", and "Docs content".
- The [check_prose](../dot-claude/hooks/check_prose.py) hook flags the prose conventions a program
  can check on every edit.
- `/simplify`, bundled with Claude Code, cleans up each change before it is committed.
- [docs-review](../dot-claude/skills/docs-review/SKILL.md),
  [dead-code-review](../dot-claude/skills/dead-code-review/SKILL.md),
  [naming-review](../dot-claude/skills/naming-review/SKILL.md), and
  [hindsight-review](../dot-claude/skills/hindsight-review/SKILL.md) find the debris a change
  leaves behind.
- [install.sh](../install.sh) puts the same rulebook on every machine.

## Known gaps

None known.
