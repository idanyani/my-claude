# Delegate authority

An agent that asks about everything spends the developer's attention; one that asks about nothing
makes the developer's decisions for them. So authority is drawn as a line: the outcome is the
developer's to decide, the method is the agent's, and the agent stops and asks only where its
work would cross that line and nothing the developer wrote down settles the question. Agents
misjudge where they stand, so the line is written in terms an agent can check, and the actions
that cannot be taken back are fenced by permissions rather than by judgment.

## In my-claude

- [resolve-issue](../dot-claude/skills/resolve-issue/SKILL.md) defines a design choice as a change
  in observable behavior the developer did not approve. The developer settles the design before
  work starts, and a choice made later waits for them before merge.
- The "Problem-solving" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) say what to search
  before asking, and that a decision the developer's stated intent settles is made and cited, not
  asked again.
- The "Issues, pull requests, and commits" conventions send every change to `main` through an
  issue and a PR.
- `permissions` in [settings.json](../dot-claude/settings.json) deny reading credential files, and
  `autoMode` tells the permission classifier which actions are routine.

## Known gaps

- *Unseen:* the agent that wrote a change also checks it for design choices, by reading its own
  diff against written rules; no program checks it.
- *Unseen:* whether a choice is hard to undo plays no part in when an agent asks.
- *Unseen:* no rule covers instructions an agent finds in content it reads, beyond what the
  permission rules fence; no incident has been seen here.
