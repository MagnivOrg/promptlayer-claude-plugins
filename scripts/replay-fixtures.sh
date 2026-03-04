#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v jq >/dev/null 2>&1; then
	echo "jq is not installed, skipping fixture replay"
	exit 0
fi

export TRACE_TO_PROMPTLAYER="true"
export PROMPTLAYER_API_KEY="pl_test_key"
export PROMPTLAYER_OTLP_ENDPOINT="http://127.0.0.1:9/v1/traces"

# Expect failure to send (no server), but script should still run.
cat plugins/pl-trace-claude-code/testdata/session_start_input.json | bash plugins/pl-trace-claude-code/hooks/session_start.sh || true

echo "Fixture replay completed"
