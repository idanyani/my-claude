# Skills and hooks are linked into ~/.claude, not shipped as a Claude Code plugin

A plugin marketplace in this repo could install, update, and retire the skills and hooks on every
machine. It is not used, because it cannot replace `install.sh`: a plugin can ship neither a
`CLAUDE.md` that loads as context nor `settings.json` keys such as permissions, model, or
`autoMode`
([plugin manifest reference](https://code.claude.com/docs/en/plugins-reference#standard-layout)),
so the conventions would still be linked and the settings merged. Moving only the skills and hooks
would add a second install path beside that one. It would gain little: a pull in a machine's clone
already updates its linked skills and hooks. And it would cost two things. Every skill would be
renamed `/<plugin>:<skill>`, which breaks the skill names the conventions and other skills use.
Auto-update for a marketplace that is not Anthropic's is off until it is turned on on each machine.
A plugin loaded in place, such as one under `~/.claude/skills/`, is worse still. Its hooks change
only at session start or `/reload-plugins`, so after a pull removes a hook script, running sessions
keep calling the missing file. Reopen this once a plugin can carry `settings.json` keys and context
instructions, so that one mechanism could replace `install.sh` entirely.
