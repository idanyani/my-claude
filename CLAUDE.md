# my-claude

- Edit `dot-claude/`, never `~/.claude` directly: the installed tree symlinks back into
  this clone (except `settings.json`, a copied snapshot).
- Re-run `./install.sh` after adding top-level entries under `dot-claude/`.
- Test with `uv run pytest`.
