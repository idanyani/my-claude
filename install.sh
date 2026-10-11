#! /bin/bash
# Install the dot-claude/ tree into ~/.claude. Generic and idempotent: no entry of dot-claude/ is
# named here except settings.json. Claude Code rewrites settings.json at runtime, which would
# sever a symlink, so it is merged into the live file (scripts/merge_settings.py); everything else
# is symlinked, and links to entries the repo dropped are retired (scripts/install_links.py).
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/dot-claude"

mkdir -p ~/.claude
python3 "$REPO/scripts/merge_settings.py" "$SRC/settings.json" ~/.claude/settings.json
python3 "$REPO/scripts/install_links.py" "$SRC" ~/.claude ~/.claude/my-claude-install-record.json
