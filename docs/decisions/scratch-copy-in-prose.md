# Scratch copies are made by a shipped script, not by steps written out in the conventions

The conventions require running tools that change files in a scratch copy of the repo. The steps
that make one are a pipeline using `git -C`, which a session in a Claude Code worktree refuses
inline but runs when the steps sit in a script file. Keeping the steps in the conventions and
telling worktree sessions to paste them into a file and run it was considered instead of shipping
`bin/scratch-copy`. It is not used, because each session would write that file its own way, so
copies could differ, and every subagent would pay the extra step. Reopen this if worktree sessions
stop refusing such pipelines, so that the steps could run as written.
