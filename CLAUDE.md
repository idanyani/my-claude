# my-claude

- Edit `dot-claude/`, never `~/.claude` directly: the installed tree symlinks back into
  this clone (except `settings.json`, merged into the live file).
- `./install.sh` runs only in the main clone, never a worktree. A pull there reruns it; after a
  commit, a reset, or a resolved merge conflict there, run it by hand.
- Test with `uv run pytest`.
- After changing a skill's `description`, or adding a skill that triggers on its own, add or adjust
  its case under `evals/` and run `claude plugin eval . --ablation none` (real model calls, so not
  in CI): the cases check which requests reach which skill.
