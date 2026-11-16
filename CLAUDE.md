# my-claude

- Edit `dot-claude/`, never `~/.claude` directly: the installed tree symlinks back into
  the main checkout (except `settings.json`, merged into the live file).
- `./install.sh` runs only in the main checkout, never a linked worktree. A pull there reruns it;
  after a commit, a reset, or a resolved merge conflict there, run it by hand.
- Test with `uv run pytest`.
