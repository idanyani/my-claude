# my-claude

- Edit `dot-claude/`, never `~/.claude` directly: the installed tree symlinks back into
  this clone (except `settings.json`, merged into the live file).
- `./install.sh` runs only in the main clone, never a worktree. A pull there reruns it; after a
  commit, a reset, or a resolved merge conflict there, run it by hand.
- Test with `uv run pytest`.
