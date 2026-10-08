#! /bin/bash
# Install the dot-claude/ tree into ~/.claude. Generic and idempotent: every top-level entry
# of dot-claude/ is handled by kind, so adding a new file or directory (agents/, commands/,
# ...) requires no change here. Symlinks keep ~/.claude live-linked to this clone (works from
# any clone location; re-running heals links after a repo move). The one exception is
# settings.json: Claude Code rewrites it at runtime, which would sever a symlink, so it is
# merged into the live file instead (scripts/merge_settings.py documents the rules).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/dot-claude"

mkdir -p ~/.claude

for entry in "$SRC"/*; do
    name="$(basename "$entry")"
    if [ "$name" = "settings.json" ]; then
        python3 "$REPO/scripts/merge_settings.py" "$entry" ~/.claude/settings.json
    elif [ -d "$entry" ]; then
        # Link per-child, not the directory itself, so machine-local entries can coexist.
        mkdir -p ~/.claude/"$name"
        for child in "$entry"/*; do
            ln -sfn "$child" ~/.claude/"$name"/"$(basename "$child")"
        done
    else
        ln -sfn "$entry" ~/.claude/"$name"
    fi
done
