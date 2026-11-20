# Learn from failures

Terms in *italics* are defined in [the index](README.md).

With *no learning from correction*, the fleet learns only when a lesson is written into *one
rulebook*, and every agent then has it at once. A written rule asks an agent to remember, and a
check a program runs stops the mistake every time, so a lesson becomes a check wherever a program
can judge it. A rejected design is recorded with why, or the next agent proposes it again.

## In my-claude

- [lessons-review](../dot-claude/skills/lessons-review/SKILL.md) finds the kinds of mistake that
  recur across sessions and proposes what would stop each.
- The "Docs content" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) keep rejected designs in
  [decision records](decisions/).
- The [require_fresh_skill](../dot-claude/hooks/require_fresh_skill.py) hook keeps a session from
  acting on a stale load of a skill.
- The "Memory discipline" conventions keep durable lessons in committed files.

## Known gaps

- *Unseen:* lessons-review runs only when the developer asks.
