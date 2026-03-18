#!/usr/bin/env python3

import json
import sys


def attribute_map(span):
    attrs = {}
    for item in span.get("attributes", []):
        key = item.get("key")
        value = item.get("value", {})
        if "stringValue" in value:
            attrs[key] = value["stringValue"]
        elif "boolValue" in value:
            attrs[key] = value["boolValue"]
        elif "intValue" in value:
            attrs[key] = value["intValue"]
        elif "doubleValue" in value:
            attrs[key] = value["doubleValue"]
        else:
            attrs[key] = None
    return attrs


def main() -> int:
    queue_file = sys.argv[1]
    with open(queue_file, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    assert lines, "expected queued OTLP payload"
    payload = json.loads(lines[-1])
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]

    tool_call_llm = None
    final_llm = None
    tool_span = None

    for span in spans:
        attrs = attribute_map(span)
        name = span.get("name")
        if name == "Tool: DocsSearch":
            tool_span = span
        elif name == "LLM Call (User)" and attrs.get("gen_ai.completion.0.tool_calls"):
            tool_call_llm = span
        elif name == "LLM call" and attrs.get("gen_ai.completion.0.content") == "All systems are operational.":
            final_llm = span

    assert tool_span is not None, "expected emitted DocsSearch tool span"
    assert tool_call_llm is not None, "expected emitted tool-call llm span"
    assert final_llm is not None, "expected emitted final llm span"

    first_attrs = attribute_map(tool_call_llm)
    final_attrs = attribute_map(final_llm)

    assert first_attrs.get("promptlayer.prompt_history_mode") == "full_session", (
        "expected full-session history marker on first emitted llm span"
    )
    assert final_attrs.get("promptlayer.prompt_history_mode") == "full_session", (
        "expected full-session history marker on final emitted llm span"
    )
    assert first_attrs.get("gen_ai.prompt.0.content") == "hello", "expected turn 1 user in tool-call prompt"
    assert first_attrs.get("gen_ai.prompt.1.content") == "Hi there", (
        "expected turn 1 assistant in tool-call prompt"
    )
    assert first_attrs.get("gen_ai.prompt.2.content") == "check the current status", (
        "expected current user in tool-call prompt"
    )
    assert "DocsSearch" in (final_attrs.get("gen_ai.prompt.3.tool_calls") or ""), (
        "expected prior tool call in final prompt"
    )
    assert final_attrs.get("gen_ai.prompt.4.content") == "Current status: all systems operational.", (
        "expected tool result in final prompt"
    )
    assert final_attrs.get("gen_ai.completion.0.content") == "All systems are operational.", (
        "expected final completion content"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        raise SystemExit(f"Assertion failed: {exc}") from exc
