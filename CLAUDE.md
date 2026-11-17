# my-claude

- Edit `dot-claude/`, never `~/.claude` directly: the installed tree symlinks back into
  the main checkout (except `settings.json`, merged into the live file).
- `./install.sh` runs only in the main checkout, never a linked worktree. A pull there reruns it;
  after a commit, a reset, or a resolved merge conflict there, run it by hand.
- Test with `uv run pytest`.
- After adding or changing a skill, add or adjust its cases under `evals/` and run
  `claude plugin eval . --ablation none --judge-model sonnet` in a scratch copy (real model calls,
  so not in CI; the default judge of `llm` graders is too small to grade by meaning over format):
  the cases check which requests reach which skill, and for some skills what it writes. A
  checkout does not work: the hard links `uv sync` makes in `.venv` fail every case.
