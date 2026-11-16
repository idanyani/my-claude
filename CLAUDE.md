# my-claude

- Edit `dot-claude/`, never `~/.claude` directly: the installed tree symlinks back into
  this clone (except `settings.json`, merged into the live file).
- `./install.sh` runs only in the main clone, never a worktree; a pull there reruns it.
- Test with `uv run pytest`.
