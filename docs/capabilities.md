# Match capabilities to tasks

A worker given a task beyond them should say so; agents rarely do, and accept any task with the
same confidence. So the manager chooses the model for the task, and trusts a model with a kind of
task only as far as its record on that kind shows.

## In my-claude

- `model` and `advisorModel` in [settings.json](../dot-claude/settings.json) pick the model every
  session works with and the stronger one it consults.

## Known gaps

- *Unseen:* every task runs on the same model, whatever its difficulty or cost.
- *Unseen:* nothing records how well a model does on each kind of task.
