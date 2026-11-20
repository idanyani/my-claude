# Match capabilities to tasks

Terms in *italics* are defined in [the index](README.md).

A person given a task beyond them tends to say so; an agent with a *misjudged own state* accepts
any task with the same confidence. So the manager uses *model choice* to fit the model to the
task, and trusts a model with a kind of task only as far as its record on that kind shows.

## In my-claude

- [settings.json](../dot-claude/settings.json) picks the model sessions work with and a stronger
  one they consult.

## Known gaps

- *Unseen:* sessions work with the same model whatever the task's difficulty or cost.
- *Unseen:* nothing records how well a model does on each kind of task.
