#! /bin/bash
# Install the dot-claude/ tree into ~/.claude. Generic and idempotent: the only entry named here
# is settings.json. Claude Code rewrites it at runtime, which would sever a symlink, so it is
# merged into the live file (scripts/merge_settings.py); every other entry is symlinked
# (scripts/install_links.py). Both steps retire what the repo dropped, using the install record.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/dot-claude"
SETTINGS="settings.json"
RECORD=~/.claude/my-claude-install-record.json

mkdir -p ~/.claude
python3 "$REPO/scripts/merge_settings.py" "$SRC/$SETTINGS" ~/.claude/"$SETTINGS" "$RECORD"
python3 "$REPO/scripts/install_links.py" "$SRC" ~/.claude "$RECORD" \
    --merged "$SETTINGS"
