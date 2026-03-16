#!/usr/bin/env python3

import base64
import json
import sys


def main() -> int:
    queue_file, expected_trace_id, expected_parent_span_id = sys.argv[1:4]

    with open(queue_file, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        raise SystemExit("Assertion failed: expected queued OTLP payload")

    payload = json.loads(lines[-1])
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    session_span = next((span for span in spans if span.get("name") == "Claude Code session"), None)
    if session_span is None:
        raise SystemExit("Assertion failed: missing Claude Code session span")

    trace_id = base64.b64decode(session_span["traceId"]).hex()
    if trace_id != expected_trace_id:
        raise SystemExit(
            f"Assertion failed: session span trace ID mismatch\n  expected: {expected_trace_id}\n  actual:   {trace_id}"
        )

    parent = session_span.get("parentSpanId")
    parent_hex = base64.b64decode(parent).hex() if parent else ""
    if parent_hex != expected_parent_span_id:
        raise SystemExit(
            f"Assertion failed: session span parent mismatch\n  expected: {expected_parent_span_id}\n  actual:   {parent_hex}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
