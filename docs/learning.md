# Learn from failures

A person corrected once stays corrected; an agent's next session starts fresh. The fleet learns
only when a lesson is written into the rulebook, and every agent then has it at once. A written
rule asks an agent to remember, and a check a program runs stops the mistake every time, so a
lesson becomes a check wherever a program can judge it. A rejected design is recorded with why, or
the next agent proposes it again.

## In my-claude

- [lessons-review](../dot-claude/skills/lessons-review/SKILL.md) finds the kinds of mistake that
  recur across sessions and proposes the check or rule that would stop each, reading GitHub
  through [github-discussion](../dot-claude/bin/github-discussion).
- The "Docs content" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) require a
  [decision record](decisions/) for a rejected design, read before a redesign.
- The [require_fresh_skill](../dot-claude/hooks/require_fresh_skill.py) hook refuses a skill's
  final steps until the session loads the skill's current text.
- The "Memory discipline" conventions keep a durable lesson in a committed file, not in an
  agent's machine-local memory.

## Known gaps

- *Unseen:* lessons-review runs only when the developer asks for it.
