# Delegate authority

Terms in *italics* are defined in [the index](README.md).

An agent that asks about everything spends the developer's attention; one that asks about nothing
makes the developer's decisions for them. So authority is drawn as a line: the outcome is the
developer's to decide, the method is the agent's, and the agent stops and asks only where its work
would cross that line and nothing the developer wrote down settles the question. An agent with a
*misjudged own state* misplaces a vague line, so the line is written in terms an agent can check,
and the actions that cannot be taken back are fenced by permissions rather than by judgment.

## In my-claude

- [resolve-issue](../dot-claude/skills/resolve-issue/SKILL.md) defines which changes are design
  choices and has the developer settle them, before work starts and, for any choice no source
  settles, before merge.
- The "Problem-solving" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) say when to ask the
  developer and when a stated intent already answers.
- The "Issues, pull requests, and commits" conventions send every change to `main` through an
  issue and a PR that resolves it, and the
  [require_skill_scripts](../dot-claude/hooks/require_skill_scripts.py) hook refuses a PR opened
  or merged outside resolve-issue's scripts ([why](decisions/every-pr-into-main.md)).
- The permission rules in [settings.json](../dot-claude/settings.json) fence what no session may
  touch, such as credential files.

## Known gaps

- *Unseen:* the agent that wrote a change also checks it for design choices, by reading its own
  diff against written rules; no program checks it.
- *Unseen:* whether a choice is hard to undo plays no part in when an agent asks.
- *Unseen:* nothing guards against an agent that *follows injected instructions* beyond what the
  permission rules fence.
