#!/bin/bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! command -v jq >/dev/null 2>&1; then
	echo "jq is not installed, skipping fixture replay"
	exit 0
fi

TRACEPARENT_VALID="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
TRACEPARENT_FUTURE="01-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-03"
TRACEPARENT_FUTURE_SUFFIXED="02-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-05-deadbeef"
TRACE_ID_VALID="4bf92f3577b34da6a3ce929d0e0e4736"
PARENT_SPAN_ID_VALID="00f067aa0ba902b7"
SESSION_ID="example-session-id"

assert_eq() {
	local actual="$1"
	local expected="$2"
	local message="$3"
	if [[ "$actual" != "$expected" ]]; then
		echo "Assertion failed: $message"
		echo "  expected: $expected"
		echo "  actual:   $actual"
		exit 1
	fi
}

assert_matches() {
	local actual="$1"
	local pattern="$2"
	local message="$3"
	if [[ ! "$actual" =~ $pattern ]]; then
		echo "Assertion failed: $message"
		echo "  pattern: $pattern"
		echo "  actual:  $actual"
		exit 1
	fi
}

state_value() {
	local home="$1"
	local sid="$2"
	local key="$3"
	jq -r ".${key} // empty" "$home/.claude/state/promptlayer_sessions/$sid.json"
}

run_hook() {
	local home="$1"
	local hook="$2"
	local input_file="$3"
	shift 3

	env \
		HOME="$home" \
		TRACE_TO_PROMPTLAYER="true" \
		PROMPTLAYER_API_KEY="pl_test_key" \
		PROMPTLAYER_OTLP_ENDPOINT="http://127.0.0.1:9/v1/traces" \
		PROMPTLAYER_OTLP_CONNECT_TIMEOUT="1" \
		PROMPTLAYER_OTLP_MAX_TIME="1" \
		"$@" \
		bash "$hook" <"$input_file"
}

assert_session_span_payload() {
	local queue_file="$1"
	local expected_trace_id="$2"
	local expected_parent_span_id="$3"

	python3 scripts/assert_session_span_payload.py "$queue_file" "$expected_trace_id" "$expected_parent_span_id"
}

new_home() {
	local dir
	dir="$(mktemp -d "${TMPDIR:-/tmp}/pl-fixture-home.XXXXXX")"
	mkdir -p "$dir/.claude/state"
	echo "$dir"
}

cleanup_home() {
	local home="$1"
	rm -rf "$home"
}

test_valid_traceparent_session_end() {
	local home
	home="$(new_home)"
	trap 'cleanup_home "$home"' RETURN

	run_hook "$home" "plugins/trace/hooks/session_start.sh" "plugins/trace/testdata/session_start_input.json" \
		"PROMPTLAYER_TRACEPARENT=$TRACEPARENT_VALID"

	assert_eq "$(state_value "$home" "$SESSION_ID" trace_id)" "$TRACE_ID_VALID" "valid traceparent should reuse upstream trace ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_parent_span_id)" "$PARENT_SPAN_ID_VALID" "valid traceparent should store upstream parent span ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_traceparent_version)" "00" "v00 traceparent should store version"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_trace_flags)" "01" "v00 traceparent should store flags"
	assert_eq "$(state_value "$home" "$SESSION_ID" trace_context_source)" "external_traceparent" "trace context source should record external parent"

	run_hook "$home" "plugins/trace/hooks/session_end.sh" "plugins/trace/testdata/session_end_input.json" \
		"PROMPTLAYER_TRACEPARENT=$TRACEPARENT_VALID"

	assert_session_span_payload "$home/.claude/state/promptlayer_otlp_queue.ndjson" "$TRACE_ID_VALID" "$PARENT_SPAN_ID_VALID"
}

test_valid_traceparent_stop_hook() {
	local home
	home="$(new_home)"
	trap 'cleanup_home "$home"' RETURN

	run_hook "$home" "plugins/trace/hooks/session_start.sh" "plugins/trace/testdata/session_start_input.json" \
		"PROMPTLAYER_TRACEPARENT=$TRACEPARENT_VALID"
	run_hook "$home" "plugins/trace/hooks/user_prompt_submit.sh" "plugins/trace/testdata/session_end_input.json" \
		"PROMPTLAYER_TRACEPARENT=$TRACEPARENT_VALID"
	run_hook "$home" "plugins/trace/hooks/stop_hook.sh" "plugins/trace/testdata/stop_input.json" \
		"PROMPTLAYER_TRACEPARENT=$TRACEPARENT_VALID"

	assert_session_span_payload "$home/.claude/state/promptlayer_otlp_queue.ndjson" "$TRACE_ID_VALID" "$PARENT_SPAN_ID_VALID"
}

test_full_history_parser() {
	local parsed_file
	parsed_file="$(mktemp "${TMPDIR:-/tmp}/pl-full-history-parse.XXXXXX")"
	trap 'rm -f "$parsed_file"' RETURN

	PL_PENDING_TOOL_CALLS='[{"tool_name":"DocsSearch","function_input":{"query":"current status"},"function_output":{"content":"Current status: all systems operational."}}]' \
		python3 plugins/trace/hooks/parse_stop_transcript.py \
		plugins/trace/testdata/stop_transcript_full_history.jsonl \
		0 \
		"$SESSION_ID" >"$parsed_file"

	python3 scripts/assert_parsed_full_history.py "$parsed_file"
}

test_full_history_stop_hook() {
	local home
	home="$(new_home)"
	trap 'cleanup_home "$home"' RETURN

	run_hook "$home" "plugins/trace/hooks/session_start.sh" "plugins/trace/testdata/session_start_input.json"
	run_hook "$home" "plugins/trace/hooks/stop_hook.sh" "plugins/trace/testdata/stop_input_full_history.json"

	python3 scripts/assert_otlp_full_history.py "$home/.claude/state/promptlayer_otlp_queue.ndjson"
}

test_missing_traceparent_fallback() {
	local home trace_id
	home="$(new_home)"
	trap 'cleanup_home "$home"' RETURN

	run_hook "$home" "plugins/trace/hooks/session_start.sh" "plugins/trace/testdata/session_start_input.json"

	trace_id="$(state_value "$home" "$SESSION_ID" trace_id)"
	assert_matches "$trace_id" '^[0-9a-f]{32}$' "missing traceparent should generate a trace ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_parent_span_id)" "" "missing traceparent should not set a parent span ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_traceparent_version)" "" "missing traceparent should not set a version"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_trace_flags)" "" "missing traceparent should not set flags"
	assert_eq "$(state_value "$home" "$SESSION_ID" trace_context_source)" "generated" "missing traceparent should record generated trace context"

	run_hook "$home" "plugins/trace/hooks/session_end.sh" "plugins/trace/testdata/session_end_input.json"

	assert_session_span_payload "$home/.claude/state/promptlayer_otlp_queue.ndjson" "$trace_id" ""
}

test_invalid_traceparent_fallback() {
	local home trace_id
	home="$(new_home)"
	trap 'cleanup_home "$home"' RETURN

	run_hook "$home" "plugins/trace/hooks/session_start.sh" "plugins/trace/testdata/session_start_input.json" \
		"PROMPTLAYER_TRACEPARENT=bogus-value"

	trace_id="$(state_value "$home" "$SESSION_ID" trace_id)"
	assert_matches "$trace_id" '^[0-9a-f]{32}$' "invalid traceparent should fall back to a generated trace ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_parent_span_id)" "" "invalid traceparent should not set a parent span ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_traceparent_version)" "" "invalid traceparent should not set a version"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_trace_flags)" "" "invalid traceparent should not set flags"
	assert_eq "$(state_value "$home" "$SESSION_ID" trace_context_source)" "generated" "invalid traceparent should record generated trace context"
}

test_non_zero_zero_version_traceparent() {
	local home
	home="$(new_home)"
	trap 'cleanup_home "$home"' RETURN

	run_hook "$home" "plugins/trace/hooks/session_start.sh" "plugins/trace/testdata/session_start_input.json" \
		"PROMPTLAYER_TRACEPARENT=$TRACEPARENT_FUTURE"

	assert_eq "$(state_value "$home" "$SESSION_ID" trace_id)" "$TRACE_ID_VALID" "non-00 traceparent should reuse upstream trace ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_parent_span_id)" "$PARENT_SPAN_ID_VALID" "non-00 traceparent should store upstream parent span ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_traceparent_version)" "01" "non-00 traceparent should store version"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_trace_flags)" "03" "non-00 traceparent should store flags"
	assert_eq "$(state_value "$home" "$SESSION_ID" trace_context_source)" "external_traceparent" "non-00 traceparent should record external parent"
}

test_future_version_traceparent_with_suffix() {
	local home
	home="$(new_home)"
	trap 'cleanup_home "$home"' RETURN

	run_hook "$home" "plugins/trace/hooks/session_start.sh" "plugins/trace/testdata/session_start_input.json" \
		"PROMPTLAYER_TRACEPARENT=$TRACEPARENT_FUTURE_SUFFIXED"

	assert_eq "$(state_value "$home" "$SESSION_ID" trace_id)" "$TRACE_ID_VALID" "future traceparent with suffix should reuse upstream trace ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_parent_span_id)" "$PARENT_SPAN_ID_VALID" "future traceparent with suffix should store upstream parent span ID"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_traceparent_version)" "02" "future traceparent with suffix should store version"
	assert_eq "$(state_value "$home" "$SESSION_ID" session_trace_flags)" "05" "future traceparent with suffix should store flags"
}

test_valid_traceparent_session_end
test_valid_traceparent_stop_hook
test_full_history_parser
test_full_history_stop_hook
test_missing_traceparent_fallback
test_invalid_traceparent_fallback
test_non_zero_zero_version_traceparent
test_future_version_traceparent_with_suffix

echo "Fixture replay completed"
