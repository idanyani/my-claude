# Set objectives and priorities

Work counts only when it serves a goal the developer holds. People push back on work that serves
nothing; agents do not, and their work costs so little that it can grow until it fills the
developer's attention. So the goals are written down where every agent reads them, and the
developer, not an agent, decides what work enters the backlog.

## In my-claude

- Each repo's README states its goals and non-goals.
- [purpose-review](../dot-claude/skills/purpose-review/SKILL.md) has the developer settle them
  and checks the repo against them; [project-review](../dot-claude/skills/project-review/SKILL.md)
  plans the large changes they call for.
- A review's findings become issues only when the developer picks them
  ([resolve-issue's workflow](../dot-claude/skills/resolve-issue/references/git-workflow.md)).

## Known gaps

- *Seen:* picking a proposed issue from a report is approval given under limited attention, not a
  priority the developer brought, yet both enter the backlog the same way.
- *Seen:* a follow-up is not weighed against the goal it serves, so follow-ups can breed
  follow-ups while the goal does not advance.
