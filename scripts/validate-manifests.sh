#!/bin/bash
set -euo pipefail

validate_json() {
	local file="$1"
	if command -v jq >/dev/null 2>&1; then
		jq -e . "$file" >/dev/null
	else
		python3 -m json.tool "$file" >/dev/null
	fi
}

validate_json .claude-plugin/marketplace.json
validate_json plugins/trace/.claude-plugin/plugin.json
validate_json plugins/trace/hooks/hooks.json

echo "Manifest validation passed"
