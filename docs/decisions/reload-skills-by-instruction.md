# A hook, not a sentence in the skills, makes sessions reload a skill before acting on it

A session loads file-issue or resolve-issue once and hours later files issues and opens PRs from
that text, after the skills changed or a compaction pushed the text far back in its context. A
sentence in those skills telling a session to load them again for each issue would not help: it
is part of the same text loaded long ago, so it drifts out of reach the same way. Instead the
`require_fresh_skill` hook refuses the commands that carry out those skills' final steps until the
session's last load of the skill is newer than the skill's files and than any compaction. Reopen
this if Claude Code reloads a skill's text by itself when its files change or a compaction comes.
