import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "plugins" / "trace" / "hooks" / "py"
sys.path.insert(0, str(HOOKS_DIR))

from state import SessionState, ensure_session_initialized


def test_ensure_session_initialized_uses_traceparent_when_available():
    state = SessionState()

    state, created = ensure_session_initialized(
        state,
        traceparent_raw="00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        generate_trace_id=lambda: "generated-trace-id",
        generate_span_id=lambda: "generated-span-id",
        requested_start_ns=123,
    )

    assert created is True
    assert state.trace_id == "4bf92f3577b34da6a3ce929d0e0e4736"
    assert state.session_parent_span_id == "00f067aa0ba902b7"
    assert state.session_span_id == "generated-span-id"
    assert state.session_start_ns == "123"
    assert state.session_init_source == "lazy_init"
    assert state.trace_context_source == "external_traceparent"


def test_ensure_session_initialized_backfills_existing_state_defaults():
    state = SessionState(
        trace_id="trace-id",
        session_span_id="span-id",
        session_start_ns="",
        pending_tool_calls="",
        session_parent_span_id="",
        session_traceparent_version="",
        session_trace_flags="",
        trace_context_source="",
        session_init_source="",
    )

    state, created = ensure_session_initialized(
        state,
        traceparent_raw="",
        generate_trace_id=lambda: "unused-trace-id",
        generate_span_id=lambda: "unused-span-id",
        requested_start_ns=999,
    )

    assert created is False
    assert state.trace_id == "trace-id"
    assert state.session_span_id == "span-id"
    assert state.session_start_ns == "999"
    assert state.pending_tool_calls == "[]"
    assert state.session_parent_span_id == ""
    assert state.session_traceparent_version == ""
    assert state.session_trace_flags == ""
    assert state.trace_context_source == "generated"
    assert state.session_init_source == "unknown"
