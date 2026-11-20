# Decompose and allocate work

A task given to one worker should be one problem, sized so its outcome can be checked. Agents can
be started on demand, so the limit on parallel work is not headcount but what can be decided and
verified. An agent handed an open design decides it alone, so work goes to an agent only once its
design is settled.

## In my-claude

- [file-issue](../dot-claude/skills/file-issue/SKILL.md) records one problem per issue, each
  resolved by its own PR.
- [resolve-issue](../dot-claude/skills/resolve-issue/SKILL.md) implements one issue end-to-end,
  and hands an issue to a subagent only once the developer settled its design.

## Known gaps

- *Unseen:* alternatives are never tried side by side, though agents could build several and let
  the developer or a test pick.
