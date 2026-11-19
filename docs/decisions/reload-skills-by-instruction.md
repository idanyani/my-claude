# A hook, not a sentence in the skills, makes sessions reload a skill before acting on it

A session loads file-issue or resolve-issue once and hours later files issues and opens PRs from
that text, after the skills changed. A sentence in those skills telling a session to load them
again for each issue would not help: it is part of the same text loaded long ago, so it goes stale
the same way. Instead the `require_fresh_skill` hook refuses the commands that carry out those
skills' final steps until the session loads the skill again. Reopen this if Claude Code reloads a
skill's text by itself when its files change.
