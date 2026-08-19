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


def test_handle_stop_hook_records_session_input_and_session_end_stamps_root(tmp_path, monkeypatch):
    from handlers import handle_session_end
    import otlp

    monkeypatch.delenv("PROMPTLAYER_TRACEPARENT", raising=False)
    sent = []
    monkeypatch.setattr(otlp, "send_payload_with_queueing", lambda ctx, payload: sent.append(payload))
    import handlers as handlers_module

    monkeypatch.setattr(handlers_module, "send_payload_with_queueing", lambda ctx, payload: sent.append(payload))
    ctx = make_ctx(tmp_path)
    handle_session_start(ctx, '{"session_id":"example-session-id"}')

    fixture = REPO_ROOT / "plugins" / "trace" / "testdata" / "stop_transcript_full_history.jsonl"
    result = handle_stop_hook(
        ctx,
        json.dumps({"session_id": "example-session-id", "transcript_path": str(fixture)}),
    )
    assert result == "example-session-id\tok"

    state = load_state(tmp_path, "example-session-id")
    assert state["session_input"] == "hello"
    assert "session_output" not in state

    sent.clear()
    handle_session_end(ctx, '{"session_id":"example-session-id"}')
    assert len(sent) == 1
    root_attrs = _root_attributes(sent[0])
    assert root_attrs["input.value"] == "hello"
    assert "output.value" not in root_attrs
    assert root_attrs["session.lifecycle"] == "complete"


def test_handle_stop_hook_keeps_trace_ids_when_session_end_races_the_parse_window(tmp_path, monkeypatch):
    # SessionEnd can run (and delete the state file) while Stop is parsing the transcript outside
    # the lock. Stop's spans must still go out on the session trace, and the file must stay deleted.
    from handlers import handle_session_end
    import handlers as handlers_module
    import otlp

    monkeypatch.delenv("PROMPTLAYER_TRACEPARENT", raising=False)
    sent = []
    monkeypatch.setattr(handlers_module, "send_payload_with_queueing", lambda ctx, payload: sent.append(payload))
    ctx = make_ctx(tmp_path)
    trace_id = handle_session_start(ctx, '{"session_id":"example-session-id"}').split("\t")[1]
    state_file = tmp_path / "sessions" / "example-session-id.json"

    real_parse = handlers_module.parse_transcript

    def parse_then_session_end(*args, **kwargs):
        parsed = real_parse(*args, **kwargs)
        handle_session_end(ctx, '{"session_id":"example-session-id"}')
        return parsed

    monkeypatch.setattr(handlers_module, "parse_transcript", parse_then_session_end)

    fixture = REPO_ROOT / "plugins" / "trace" / "testdata" / "stop_transcript_full_history.jsonl"
    result = handle_stop_hook(ctx, json.dumps({"session_id": "example-session-id", "transcript_path": str(fixture)}))
    assert result == "example-session-id\tok"

    stop_spans = sent[-1]["resourceSpans"][0]["scopeSpans"][0]["spans"]
    expected_trace_id = otlp.hex_to_base64(trace_id)
    assert len(stop_spans) == 4
    assert {span["traceId"] for span in stop_spans} == {expected_trace_id}
    assert sum(1 for span in stop_spans if not span.get("parentSpanId")) == 1
    assert _root_attributes(sent[-1])["input.value"] == "hello"
    assert not state_file.exists()


def _root_attributes(payload):
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    root = next(span for span in spans if not span.get("parentSpanId"))
    return {
        attr["key"]: next(iter(attr["value"].values()))
        for attr in root["attributes"]
    }
