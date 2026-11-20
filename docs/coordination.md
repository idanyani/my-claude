# Coordinate shared resources

People who share a workspace notice each other; agents do not. Several sessions can edit one
checkout, fill one machine's memory, or delete what another relies on, and none of them sees it
coming. So each agent works in a space of its own, and what agents share -- a machine, a cloud
resource, a component other repos depend on -- is used through a mechanism that keeps one from
starving or breaking another. The environment that runs the agents supplies the mechanisms for
its own resources; my-claude supplies those that hold in any environment.

## In my-claude

- resolve-issue works in a git worktree by default
  ([its workflow](../dot-claude/skills/resolve-issue/references/git-workflow.md)).
- [scratch-copy](../dot-claude/bin/scratch-copy) makes a copy without git data for tools that
  change files, as the "Scratch copies" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md)
  require.
- The "Background work" conventions bound waits and polls, and the
  [report_stale_shells](../dot-claude/hooks/report_stale_shells.py) hook reports background shells
  that outlived their work.
- The "Small and neat code" conventions keep a shared component from naming its consumers, so
  adding or retiring one needs no edit to it.

## Known gaps

- *Seen, accepted:* a change to the shared conventions breaks a check in each repo that keeps a
  copy of them, until that copy is synced.
