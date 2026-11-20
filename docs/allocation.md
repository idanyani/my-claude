# Decompose and allocate work

Terms in *italics* are defined in [the index](README.md).

A task given to one worker should be one problem, sized so its outcome can be checked. With
*on-demand workers*, the limit on parallel work is not headcount but what the developer can decide
and verify. An agent handed an open design decides it alone, so work goes to an agent only once its
design is settled.

## In my-claude

- [file-issue](../dot-claude/skills/file-issue/SKILL.md) records one problem per issue.
- [resolve-issue](../dot-claude/skills/resolve-issue/SKILL.md) implements one issue end-to-end, and
  hands issues to subagents only under the developer's settled designs.

## Known gaps

- *Unseen:* alternatives are never tried side by side, though agents could build several and let
  the developer or a test pick.
