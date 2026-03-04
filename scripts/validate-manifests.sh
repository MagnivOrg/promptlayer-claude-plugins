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

# Verify plugin version in lib.sh matches marketplace.json
manifest_version="$(jq -r '.version' .claude-plugin/marketplace.json)"
lib_version="$(sed -n 's/^export PL_PLUGIN_VERSION="\(.*\)"/\1/p' plugins/trace/hooks/lib.sh)"
if [[ "$manifest_version" != "$lib_version" ]]; then
	echo "ERROR: version mismatch — marketplace.json=$manifest_version lib.sh=$lib_version" >&2
	exit 1
fi

echo "Manifest validation passed"
