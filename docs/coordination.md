# Coordinate shared resources

Terms in *italics* are defined in [the index](README.md).

People who share a workspace notice each other; agents are *unaware of peers*. So each agent works
in a space of its own, and what agents share -- a machine, a cloud resource, a component other
repos depend on -- is used through a mechanism that keeps one from starving or breaking another.
The environment that runs the agents supplies the mechanisms for its own resources; my-claude
supplies those that hold in any environment.

## In my-claude

- resolve-issue works in a git worktree by default
  ([its workflow](../dot-claude/skills/resolve-issue/references/git-workflow.md)).
- [scratch-copy](../dot-claude/bin/scratch-copy) gives tools that change files a copy of their own,
  as the "Scratch copies" conventions in [CLAUDE.md](../dot-claude/CLAUDE.md) require.
- The "Background work" conventions keep waits and polls from outliving their work, and the
  [report_stale_shells](../dot-claude/hooks/report_stale_shells.py) hook reports those that did.
- The "Small and neat code" conventions keep a shared component independent of its consumers.

## Known gaps

None known.
