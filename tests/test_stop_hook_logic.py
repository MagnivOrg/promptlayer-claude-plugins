import pathlib
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "plugins" / "trace" / "hooks" / "py"
sys.path.insert(0, str(HOOKS_DIR))

from stop_parser import build_stop_hook_span_specs, parse_transcript


SESSION_ID = "example-session-id"


def test_parse_transcript_full_history_fixture_preserves_expected_spans():
    parsed = parse_transcript(
        str(REPO_ROOT / "plugins" / "trace" / "testdata" / "stop_transcript_full_history.jsonl"),
        0,
        [
            {
                "tool_name": "DocsSearch",
                "function_input": {"query": "current status"},
                "function_output": {"content": "Current status: all systems operational."},
            }
        ],
        SESSION_ID,
    )

    llms = parsed["llms"]
    tools = parsed["tools"]

    assert len(llms) == 2
    assert len(tools) == 1
    assert llms[0]["name"] == "LLM Call (User)"
    assert llms[1]["name"] == "LLM call"
    assert tools[0]["name"] == "Tool: DocsSearch"
    assert llms[0]["attributes"]["promptlayer.prompt_history_mode"] == "full_session"
    assert llms[1]["attributes"]["gen_ai.completion.0.content"] == "All systems are operational."


def test_build_stop_hook_span_specs_builds_root_and_child_span_specs():
    parsed = {
        "turn": {"start_ns": 100, "end_ns": 220},
        "tools": [
            {
                "name": "Tool: DocsSearch",
                "start_ns": 110,
                "end_ns": 150,
                "attributes": {"tool_name": "DocsSearch"},
            }
        ],
        "llms": [
            {
                "name": "LLM Call (User)",
                "start_ns": 150,
                "end_ns": 220,
                "attributes": {"gen_ai.request.model": "claude"},
            }
        ],
    }

    span_specs = build_stop_hook_span_specs(
        parsed=parsed,
        trace_id="trace1234",
        session_span_id="rootspan",
        session_parent_span_id="parentspan",
        session_start_ns="90",
        session_init_source="session_start_hook",
        generate_span_id=lambda: "childspan",
    )

    assert len(span_specs) == 3
    assert span_specs[0].name == "Claude Code session"
    assert span_specs[0].span_id == "rootspan"
    assert span_specs[0].parent_span_id == "parentspan"
    assert span_specs[0].attrs["hook"] == "Stop"
    assert span_specs[0].attrs["session.lifecycle"] == "in_progress"

    assert span_specs[1].name == "Tool: DocsSearch"
    assert span_specs[1].parent_span_id == "rootspan"
    assert span_specs[1].kind == "3"

    assert span_specs[2].name == "LLM Call (User)"
    assert span_specs[2].parent_span_id == "rootspan"
    assert span_specs[2].kind == "3"


def test_build_stop_hook_span_specs_uses_lazy_init_session_attrs():
    parsed = {"turn": {"start_ns": 100, "end_ns": 120}, "tools": [], "llms": []}

    span_specs = build_stop_hook_span_specs(
        parsed=parsed,
        trace_id="trace1234",
        session_span_id="rootspan",
        session_parent_span_id="",
        session_start_ns="90",
        session_init_source="lazy_init",
        generate_span_id=lambda: "unused",
    )

    assert len(span_specs) == 1
    assert span_specs[0].attrs["hook"] == "StopFallback"
    assert span_specs[0].attrs["session.lifecycle"] == "stop_fallback"


def test_session_input_from_parsed_picks_first_user_prompt():
    from stop_parser import session_input_from_parsed

    parsed = parse_transcript(
        str(REPO_ROOT / "plugins" / "trace" / "testdata" / "stop_transcript_full_history.jsonl"),
        0,
        [
            {
                "tool_name": "DocsSearch",
                "function_input": {"query": "current status"},
                "function_output": {"content": "Current status: all systems operational."},
            }
        ],
        SESSION_ID,
    )

    assert session_input_from_parsed(parsed) == "hello"


def test_session_input_from_parsed_is_empty_without_llms():
    from stop_parser import session_input_from_parsed

    assert session_input_from_parsed({"turn": {}, "tools": [], "llms": []}) == ""


def test_build_stop_hook_span_specs_stamps_session_input_on_root_only():
    span_specs = build_stop_hook_span_specs(
        parsed={"turn": {"start_ns": 10, "end_ns": 20}, "tools": [], "llms": []},
        trace_id="a" * 32,
        session_span_id="b" * 16,
        session_parent_span_id="",
        session_start_ns="10",
        session_init_source="session_start_hook",
        generate_span_id=lambda: "c" * 16,
        session_input="Where is my order?",
    )

    root = span_specs[0]
    assert root.attrs["input.value"] == "Where is my order?"
    # Output is deliberately left to the request logs
    assert "output.value" not in root.attrs


def test_build_stop_hook_span_specs_omits_missing_session_input():
    span_specs = build_stop_hook_span_specs(
        parsed={"turn": {"start_ns": 10, "end_ns": 20}, "tools": [], "llms": []},
        trace_id="a" * 32,
        session_span_id="b" * 16,
        session_parent_span_id="",
        session_start_ns="10",
        session_init_source="session_start_hook",
        generate_span_id=lambda: "c" * 16,
    )

    assert "input.value" not in span_specs[0].attrs
