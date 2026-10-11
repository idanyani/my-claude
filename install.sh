#! /bin/bash
# Install the dot-claude/ tree into ~/.claude. Generic and idempotent: the only entry named here
# is settings.json. Claude Code rewrites it at runtime, which would sever a symlink, so it is
# merged into the live file (scripts/merge_settings.py); every other entry is symlinked, and links
# to entries the repo dropped are retired (scripts/install_links.py).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/dot-claude"
SETTINGS="settings.json"

mkdir -p ~/.claude
python3 "$REPO/scripts/merge_settings.py" "$SRC/$SETTINGS" ~/.claude/"$SETTINGS"
python3 "$REPO/scripts/install_links.py" "$SRC" ~/.claude ~/.claude/my-claude-install-record.json \
    --merged "$SETTINGS"
