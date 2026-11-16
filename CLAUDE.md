# my-claude

- Edit `dot-claude/`, never `~/.claude` directly: the installed tree symlinks back into
  this clone (except `settings.json`, merged into the live file).
- `./install.sh` runs only in the main clone, never a worktree. A pull there reruns it; after a
  commit, a reset, or a resolved merge conflict there, run it by hand.
- Test with `uv run pytest`.
- After adding a skill or changing its `description`, add or adjust its case under `evals/` and
  run `claude plugin eval . --ablation none` in a scratch copy (real model calls, so not in CI): the
  cases check which requests reach which skill. A checkout does not work: the hard links `uv sync`
  makes in `.venv` fail every case.
