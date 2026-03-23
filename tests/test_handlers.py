import json
import pathlib
import sys
from types import SimpleNamespace


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "plugins" / "trace" / "hooks" / "py"
sys.path.insert(0, str(HOOKS_DIR))

from handlers import handle_post_tool_use, handle_session_start, handle_stop_hook


def make_ctx(tmp_path):
    (tmp_path / "sessions").mkdir(exist_ok=True)
    (tmp_path / "locks").mkdir(exist_ok=True)
    return SimpleNamespace(
        log_file=str(tmp_path / "hook.log"),
        queue_file=str(tmp_path / "queue.ndjson"),
        session_state_dir=str(tmp_path / "sessions"),
        lock_dir=str(tmp_path / "locks"),
        debug="false",
        api_key="pl_test_key",
        otlp_endpoint="http://127.0.0.1:9/v1/traces",
        queue_drain_limit=10,
        otlp_connect_timeout=1,
        otlp_max_time=1,
        plugin_version="1.0.0",
        cc_version="test",
        user_agent="promptlayer-test",
    )


def load_state(tmp_path, session_id):
    with open(tmp_path / "sessions" / f"{session_id}.json", encoding="utf-8") as f:
        return json.load(f)


def test_handle_session_start_creates_state_file(tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPTLAYER_TRACEPARENT", raising=False)
    ctx = make_ctx(tmp_path)

    result = handle_session_start(ctx, '{"session_id":"example-session-id"}')

    assert result.endswith("\tcaptured")
    state = load_state(tmp_path, "example-session-id")
    assert len(state["trace_id"]) == 32
    assert len(state["session_span_id"]) == 16
    assert state["trace_context_source"] == "generated"


def test_handle_post_tool_use_appends_pending_tool_call(tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPTLAYER_TRACEPARENT", raising=False)
    ctx = make_ctx(tmp_path)
    handle_session_start(ctx, '{"session_id":"example-session-id"}')

    result = handle_post_tool_use(
        ctx,
        json.dumps(
            {
                "session_id": "example-session-id",
                "tool_name": "DocsSearch",
                "tool_input": {"query": "status"},
                "tool_response": {"content": "ok"},
            }
        ),
    )

    assert result == "example-session-id\tDocsSearch"
    state = load_state(tmp_path, "example-session-id")
    pending = json.loads(state["pending_tool_calls"])
    assert len(pending) == 1
    assert pending[0]["tool_name"] == "DocsSearch"
    assert pending[0]["function_input"] == {"query": "status"}


def test_handle_stop_hook_returns_missing_transcript_marker(tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPTLAYER_TRACEPARENT", raising=False)
    ctx = make_ctx(tmp_path)
    handle_session_start(ctx, '{"session_id":"example-session-id"}')

    result = handle_stop_hook(
        ctx,
        json.dumps(
            {
                "session_id": "example-session-id",
                "transcript_path": str(tmp_path / "missing.jsonl"),
            }
        ),
    )

    assert result == "example-session-id\tmissing_transcript"
