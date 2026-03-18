#!/usr/bin/env python3

import json
import sys


def main() -> int:
    parsed_file = sys.argv[1]
    with open(parsed_file, encoding="utf-8") as f:
        parsed = json.load(f)

    llms = parsed.get("llms", [])
    tools = parsed.get("tools", [])

    assert len(llms) == 2, f"expected 2 llm spans, got {len(llms)}"
    assert len(tools) == 1, f"expected 1 tool span, got {len(tools)}"

    tool_call_llm = llms[0]
    final_llm = llms[1]

    assert tool_call_llm["name"] == "LLM Call (User)", "expected first llm to be user-initiated"
    assert final_llm["name"] == "LLM call", "expected final llm to be tool-result continuation"

    first_attrs = tool_call_llm["attributes"]
    final_attrs = final_llm["attributes"]

    assert first_attrs.get("promptlayer.prompt_history_mode") == "full_session", (
        "expected full-session history marker on first llm span"
    )
    assert final_attrs.get("promptlayer.prompt_history_mode") == "full_session", (
        "expected full-session history marker on final llm span"
    )

    assert first_attrs.get("gen_ai.prompt.0.content") == "hello", "expected first prompt item to include turn 1 user"
    assert first_attrs.get("gen_ai.prompt.1.content") == "Hi there", (
        "expected first prompt item to include turn 1 assistant"
    )
    assert first_attrs.get("gen_ai.prompt.2.content") == "check the current status", (
        "expected first tool-call prompt to include current user message"
    )
    assert first_attrs.get("gen_ai.prompt.2.role") == "user", "expected third prompt item to be current user"
    assert "DocsSearch" in (first_attrs.get("gen_ai.completion.0.tool_calls") or ""), (
        "expected tool call completion on first llm span"
    )

    assert final_attrs.get("gen_ai.prompt.0.content") == "hello", "expected final prompt to retain turn 1 user"
    assert final_attrs.get("gen_ai.prompt.1.content") == "Hi there", (
        "expected final prompt to retain turn 1 assistant"
    )
    assert final_attrs.get("gen_ai.prompt.2.content") == "check the current status", (
        "expected final prompt to retain current user message"
    )
    assert final_attrs.get("gen_ai.prompt.3.role") == "assistant", (
        "expected final prompt to include prior assistant tool-call message"
    )
    assert "DocsSearch" in (final_attrs.get("gen_ai.prompt.3.tool_calls") or ""), (
        "expected final prompt to include prior assistant tool call"
    )
    assert final_attrs.get("gen_ai.prompt.4.role") == "tool", (
        "expected final prompt to include tool result role"
    )
    assert final_attrs.get("gen_ai.prompt.4.content") == "Current status: all systems operational.", (
        "expected final prompt to include tool result content"
    )
    assert final_attrs.get("gen_ai.completion.0.content") == "All systems are operational.", (
        "expected final completion content"
    )
    assert tools[0]["name"] == "Tool: DocsSearch", "expected tool span name"
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        raise SystemExit(f"Assertion failed: {exc}") from exc
