#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=plugins/pl-trace-claude-code/hooks/lib.sh
source "$SCRIPT_DIR/lib.sh"

tracing_enabled || exit 0
check_requirements || exit 0

input="$(cat)"
session_id="$(echo "$input" | jq -r '.session_id // empty')"
[[ -z "$session_id" ]] && exit 0

acquire_session_lock "$session_id" || exit 0
trap 'release_session_lock' EXIT

trace_id="$(get_session_state "$session_id" trace_id)"
session_span_id="$(get_session_state "$session_id" session_span_id)"
session_start_ns="$(get_session_state "$session_id" session_start_ns)"
session_root_emitted="$(get_session_state "$session_id" session_root_emitted)"
stop_in_flight="$(get_session_state "$session_id" stop_in_flight)"
current_turn_span_id="$(get_session_state "$session_id" current_turn_span_id)"
[[ -z "$trace_id" || -z "$session_span_id" ]] && exit 0
[[ -z "$session_start_ns" ]] && session_start_ns="$(now_ns)"
[[ -z "$stop_in_flight" ]] && stop_in_flight="false"

if [[ -n "$current_turn_span_id" || "$stop_in_flight" == "true" ]]; then
	set_session_state "$session_id" session_end_requested "true"
	log "INFO" "SessionEnd deferred until Stop session_id=$session_id"
	exit 0
fi

should_emit_root="false"
if [[ "$session_root_emitted" != "true" ]]; then
	should_emit_root="true"
fi

release_session_lock
trap - EXIT

if [[ "$should_emit_root" == "true" ]]; then
	end_ns="$(now_ns)"
	attrs='{"source":"claude-code","hook":"SessionEnd","node_type":"WORKFLOW"}'
	emit_span "$trace_id" "$session_span_id" "" "Claude Code session" "1" "$session_start_ns" "$end_ns" "$attrs" || true
fi

acquire_session_lock "$session_id" || exit 0
trap 'release_session_lock' EXIT

stop_in_flight="$(get_session_state "$session_id" stop_in_flight)"
current_turn_span_id="$(get_session_state "$session_id" current_turn_span_id)"
[[ -z "$stop_in_flight" ]] && stop_in_flight="false"
if [[ -n "$current_turn_span_id" || "$stop_in_flight" == "true" ]]; then
	set_session_state "$session_id" session_end_requested "true"
	log "INFO" "SessionEnd deferred until Stop session_id=$session_id"
	exit 0
fi

if [[ "$should_emit_root" == "true" ]]; then
	set_session_state "$session_id" session_root_emitted "true"
fi
rm -f "$PL_SESSION_STATE_DIR/$session_id.json"
log "INFO" "SessionEnd finalized session_id=$session_id"
