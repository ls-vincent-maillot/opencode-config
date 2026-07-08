#!/usr/bin/env bash
#
# Back up (or restore) personal OpenCode config into this repo.
# The live files are never moved — only copied. Structure stays untouched.
#
# Usage:
#   ./sync-opencode-config.sh             # backup live config -> repo, then local commit
#   ./sync-opencode-config.sh --no-commit # backup only, no commit
#   ./sync-opencode-config.sh --restore   # repo -> live config (OVERWRITES live files)
#
# Never pushes — run `git -C <repo> push` yourself when ready.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GLOBAL_DIR="$HOME/.config/opencode"
WEBPOS_DIR="/Volumes/dev/webPOS"

MODE="backup"
DO_COMMIT=1
for arg in "$@"; do
	case "$arg" in
	--restore) MODE="restore" ;;
	--no-commit) DO_COMMIT=0 ;;
	*)
		echo "Unknown arg: $arg" >&2
		exit 1
		;;
	esac
done

need() { [ -e "$1" ] || { echo "⚠ missing: $1 (skipped)" >&2; return 1; }; }

backup() {
	echo "→ Backing up live OpenCode config into $REPO_DIR"
	mkdir -p "$REPO_DIR/global" "$REPO_DIR/webpos/dot-opencode"

	# Global config
	need "$GLOBAL_DIR/opencode.json" && cp "$GLOBAL_DIR/opencode.json" "$REPO_DIR/global/opencode.json"
	need "$GLOBAL_DIR/AGENTS.md" && cp "$GLOBAL_DIR/AGENTS.md" "$REPO_DIR/global/AGENTS.md"
	need "$GLOBAL_DIR/opencode-ghostty-notifier.json" && cp "$GLOBAL_DIR/opencode-ghostty-notifier.json" "$REPO_DIR/global/opencode-ghostty-notifier.json"

	# webPOS project: root config + the .opencode payload
	need "$WEBPOS_DIR/opencode.json" && cp "$WEBPOS_DIR/opencode.json" "$REPO_DIR/webpos/opencode.json"
	if need "$WEBPOS_DIR/.opencode/skills"; then
		rsync -aL --delete "$WEBPOS_DIR/.opencode/skills/" "$REPO_DIR/webpos/dot-opencode/skills/"
	fi
	if need "$WEBPOS_DIR/.opencode/rules"; then
		rsync -a --delete "$WEBPOS_DIR/.opencode/rules/" "$REPO_DIR/webpos/dot-opencode/rules/"
	fi
	need "$WEBPOS_DIR/.opencode/memories.md" && cp "$WEBPOS_DIR/.opencode/memories.md" "$REPO_DIR/webpos/dot-opencode/memories.md"

	echo "✓ Backup done"
}

restore() {
	echo "→ Restoring config FROM $REPO_DIR into live locations (overwrites)"
	mkdir -p "$GLOBAL_DIR" "$WEBPOS_DIR/.opencode"

	need "$REPO_DIR/global/opencode.json" && cp "$REPO_DIR/global/opencode.json" "$GLOBAL_DIR/opencode.json"
	need "$REPO_DIR/global/AGENTS.md" && cp "$REPO_DIR/global/AGENTS.md" "$GLOBAL_DIR/AGENTS.md"
	need "$REPO_DIR/global/opencode-ghostty-notifier.json" && cp "$REPO_DIR/global/opencode-ghostty-notifier.json" "$GLOBAL_DIR/opencode-ghostty-notifier.json"
	need "$REPO_DIR/webpos/opencode.json" && cp "$REPO_DIR/webpos/opencode.json" "$WEBPOS_DIR/opencode.json"
	if need "$REPO_DIR/webpos/dot-opencode/skills"; then
		rsync -a --delete "$REPO_DIR/webpos/dot-opencode/skills/" "$WEBPOS_DIR/.opencode/skills/"
	fi
	if need "$REPO_DIR/webpos/dot-opencode/rules"; then
		rsync -a --delete "$REPO_DIR/webpos/dot-opencode/rules/" "$WEBPOS_DIR/.opencode/rules/"
	fi
	need "$REPO_DIR/webpos/dot-opencode/memories.md" && cp "$REPO_DIR/webpos/dot-opencode/memories.md" "$WEBPOS_DIR/.opencode/memories.md"
	# Recreate the singular-name compat symlink OpenCode also looks for.
	ln -sfn skills "$WEBPOS_DIR/.opencode/skill"

	echo "✓ Restore done"
}

if [ "$MODE" = "restore" ]; then
	restore
	exit 0
fi

backup

if [ "$DO_COMMIT" = "1" ]; then
	git -C "$REPO_DIR" add -A
	if git -C "$REPO_DIR" diff --cached --quiet; then
		echo "• No changes to commit."
	else
		git -C "$REPO_DIR" commit -q -m "sync: $(date '+%Y-%m-%d %H:%M:%S')"
		echo "✓ Committed locally. Push when ready: git -C $REPO_DIR push"
	fi
fi
