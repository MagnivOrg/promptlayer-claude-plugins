#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="$HOME/.claude/plugins/marketplaces/promptlayer-claude-plugin"
PLUGIN="pl-trace-claude-code@promptlayer-claude-plugin"
SETUP_SCRIPT="$TARGET/plugins/pl-trace-claude-code/setup.sh"

mkdir -p "$(dirname "$TARGET")"
rm -rf "$TARGET"
ln -s "$REPO_ROOT" "$TARGET"

echo "Symlinked $REPO_ROOT -> $TARGET"

claude plugin marketplace add "$REPO_ROOT"
echo "Registered marketplace from local path: $REPO_ROOT"

claude plugin install "$PLUGIN"
echo "Installed plugin: $PLUGIN"

echo "Running setup: $SETUP_SCRIPT"
"$SETUP_SCRIPT"
