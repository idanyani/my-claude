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

# ~/.claude and the clone's shared git hooks link into the checkout that runs this; a linked
# worktree is deleted once its branch merges, which would leave every link dangling.
GIT_DIR_OF_REPO="$(git -C "$REPO" rev-parse --absolute-git-dir)"
COMMON_GIT_DIR="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)"
if [ "$GIT_DIR_OF_REPO" != "$COMMON_GIT_DIR" ]; then
    echo "install.sh: run it from the clone's main checkout, not from a linked worktree" >&2
    exit 1
fi

mkdir -p ~/.claude
python3 "$REPO/scripts/merge_settings.py" "$SRC/$SETTINGS" ~/.claude/"$SETTINGS" "$RECORD"
python3 "$REPO/scripts/install_links.py" "$SRC" ~/.claude "$RECORD" \
    --merged "$SETTINGS"
HOOKS="$(git -C "$REPO" rev-parse --path-format=absolute --git-path hooks)"
mkdir -p "$HOOKS"
for hook in post-merge post-checkout post-rewrite; do
    ln -sf "$REPO/scripts/reinstall-on-update" "$HOOKS/$hook"
done
