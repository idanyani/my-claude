# Report to steer

The developer steers the fleet from what its agents report, often after days away. A report that
takes long to read, hides the choices made without the developer, or asks more than a few things
spends the attention the central principle values most. So a report fits on one screen, tags every
claim by how well it is backed, lists every choice made alone, and ends on the few decisions the
developer must make.

## In my-claude

- The [brief](../dot-claude/skills/brief/SKILL.md) skill sets the format of every report and
  every question that needs background.
- The "Messages to the user" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) say when a report
  takes that format.
- A PR lists a review's findings about failures no run has shown as known limits, where a later
  reader finds them, instead of offering them as work
  ([resolve-issue's workflow](../dot-claude/skills/resolve-issue/references/git-workflow.md)).

## Known gaps

- *Seen:* the developer's answers to agents' questions exist only in session transcripts, which
  stay on one machine and expire, so no one can later tell what was asked and how it was answered.
