# A subagent that lost its worktree while paused is replaced, not kept alive or given a new one

A worktree subagent that stops to return a design choice before changing any file loses its
worktree, since Claude Code deletes an agent's unchanged worktree when it stops. Four ways to keep
the subagent itself were weighed instead of spawning a replacement. Waiting for the answer without
stopping fails because a subagent's wait returns at once while nothing of its own runs, so waiting
hours for the user means polling. Making a new worktree, or switching into one the spawning session
made, fails because Claude Code refuses both to an agent isolated in a worktree. Committing a
placeholder before pausing, so the worktree counts as changed, puts commits on the branch that
record nothing. Reopen this if Claude Code keeps a paused agent's worktree, lets an isolated agent
switch worktrees, or lets a subagent wait for a message without polling.
