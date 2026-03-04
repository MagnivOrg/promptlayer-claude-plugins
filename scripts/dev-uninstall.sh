#!/bin/bash
set -euo pipefail

PLUGIN="pl-trace-claude-code@promptlayer-claude-plugin"
MARKETPLACE="promptlayer-claude-plugin"

for scope in user project local; do
	claude plugin uninstall --scope "$scope" "$PLUGIN" >/dev/null 2>&1 || true
done
echo "Uninstalled plugin (if present): $PLUGIN"

claude plugin marketplace remove "$MARKETPLACE" >/dev/null 2>&1 || true
echo "Removed marketplace (if present): $MARKETPLACE"

rm -rf "$HOME/.claude/plugins/marketplaces/$MARKETPLACE"
rm -rf "$HOME/.claude/plugins/cache/$MARKETPLACE"
rm -f "$HOME/.claude/state/promptlayer_hook.log"
rm -f "$HOME/.claude/state/promptlayer_otlp_queue.ndjson"
rm -rf "$HOME/.claude/state/promptlayer_sessions"
rm -rf "$HOME/.claude/state/promptlayer_locks"

echo "Removed PromptLayer local artifacts from ~/.claude"
