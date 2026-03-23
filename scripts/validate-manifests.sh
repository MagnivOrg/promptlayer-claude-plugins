#!/bin/bash
set -euo pipefail

validate_json() {
	local file="$1"
	python3 -m json.tool "$file" >/dev/null
}

validate_json .claude-plugin/marketplace.json
validate_json plugins/trace/.claude-plugin/plugin.json
validate_json plugins/trace/hooks/hooks.json

# Verify plugin version in lib.sh matches marketplace.json
manifest_version="$(python3 -c 'import json; print(json.load(open(".claude-plugin/marketplace.json", encoding="utf-8"))["version"])')"
lib_version="$(sed -n 's/^export PL_PLUGIN_VERSION="\(.*\)"/\1/p' plugins/trace/hooks/lib.sh)"
if [[ "$manifest_version" != "$lib_version" ]]; then
	echo "ERROR: version mismatch — marketplace.json=$manifest_version lib.sh=$lib_version" >&2
	exit 1
fi

echo "Manifest validation passed"
