#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "claude-agent-sdk>=0.1.45",
# ]
# ///

"""End-to-end smoke test for pl-trace-claude-code via Claude Agent SDK.

The smoke test launches a local OTLP HTTP collector, runs a short Claude session
with the plugin enabled, then asserts that OTLP payloads were actually received.
"""

import asyncio
import contextlib
import json
import os
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_PATH = REPO_ROOT / "plugins" / "pl-trace-claude-code"


class _CollectorHandler(BaseHTTPRequestHandler):
    payloads = []

    def do_POST(self) -> None:  # noqa: N802 - HTTP handler name from stdlib.
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        self.__class__.payloads.append(
            {
                "path": self.path,
                "headers": dict(self.headers),
                "body": body,
            }
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, _format: str, *_args) -> None:
        return


@contextlib.contextmanager
def local_otlp_collector():
    _CollectorHandler.payloads = []
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]

    server = ThreadingHTTPServer(("127.0.0.1", port), _CollectorHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}/v1/traces", _CollectorHandler.payloads
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1.0)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def wait_for_hook_outputs(log_file: Path, collected_payloads: list[dict]) -> tuple[str, list[dict]]:
    """Wait briefly for async hooks to finish emitting spans."""
    deadline = time.time() + 8.0
    prev_count = -1
    stable_ticks = 0
    while time.time() < deadline:
        count = len(collected_payloads)
        if count == prev_count:
            stable_ticks += 1
        else:
            prev_count = count
            stable_ticks = 0

        log_text = read_text(log_file)
        if ("Stop finalized" in log_text or "SessionEnd finalized" in log_text) and stable_ticks >= 3:
            break

        time.sleep(0.2)

    return read_text(log_file), list(collected_payloads)


def parse_otlp_spans(payloads: list[dict]) -> tuple[int, int, list[dict]]:
    parsed_payloads = 0
    payload_schema_matches = 0
    spans: list[dict] = []

    for item in payloads:
        try:
            body = json.loads(item.get("body", ""))
        except json.JSONDecodeError:
            continue

        parsed_payloads += 1
        if (
            item.get("path") == "/v1/traces"
            and isinstance(body, dict)
            and isinstance(body.get("resourceSpans"), list)
            and body["resourceSpans"]
        ):
            payload_schema_matches += 1

        for resource_span in body.get("resourceSpans", []):
            for scope_span in resource_span.get("scopeSpans", []):
                for span in scope_span.get("spans", []):
                    spans.append(span)

    return parsed_payloads, payload_schema_matches, spans


def validate_span_graph(spans: list[dict]) -> tuple[list[str], dict]:
    errors: list[str] = []
    if not spans:
        return ["No spans found in captured OTLP payloads"], {}

    traces: dict[str, list[dict]] = {}
    for span in spans:
        trace_id = span.get("traceId")
        span_id = span.get("spanId")
        if not trace_id:
            errors.append("Span missing traceId")
            continue
        if not span_id:
            errors.append("Span missing spanId")
            continue
        traces.setdefault(trace_id, []).append(span)

    trace_count = len(traces)
    if trace_count != 1:
        errors.append(f"Expected exactly 1 trace, found {trace_count}")

    root_count = 0
    edge_count = 0
    session_root_found = False
    unresolved_parent_ids: set[str] = set()

    for trace_id, trace_spans in traces.items():
        by_id: dict[str, dict] = {}
        for span in trace_spans:
            span_id = span["spanId"]
            if span_id in by_id:
                errors.append(f"Duplicate spanId in trace {trace_id}")
            by_id[span_id] = span

        trace_roots = 0
        for span in trace_spans:
            parent_id = span.get("parentSpanId")

            start_raw = span.get("startTimeUnixNano")
            end_raw = span.get("endTimeUnixNano")
            try:
                start_ns = int(start_raw)
                end_ns = int(end_raw)
                if end_ns < start_ns:
                    errors.append(f"Span has end < start: {span.get('name', '<unnamed>')}")
            except (TypeError, ValueError):
                errors.append(f"Span has non-integer timestamps: {span.get('name', '<unnamed>')}")

            if not parent_id:
                trace_roots += 1
                if span.get("name") == "Claude Code session":
                    session_root_found = True
            else:
                edge_count += 1
                if parent_id not in by_id:
                    unresolved_parent_ids.add(parent_id)

        # Partial capture is expected in some SDK flows; allow no explicit root
        # as long as unresolved ancestry is small and internally consistent.
        if trace_roots == 0 and not unresolved_parent_ids:
            errors.append(f"Trace {trace_id} has no root and no unresolved parent")
        root_count += trace_roots

        for span in trace_spans:
            seen: set[str] = set()
            current = span
            while current.get("parentSpanId"):
                parent_id = current["parentSpanId"]
                if parent_id in seen:
                    errors.append(f"Cycle detected in trace {trace_id}")
                    break
                seen.add(parent_id)
                parent = by_id.get(parent_id)
                if parent is None:
                    break
                current = parent

    if edge_count == 0:
        errors.append("Trace graph has no parent-child edges")
    if len(unresolved_parent_ids) > 1:
        errors.append(
            f"Too many unresolved parent IDs ({len(unresolved_parent_ids)}), expected at most 1"
        )

    metrics = {
        "span_count": len(spans),
        "trace_count": trace_count,
        "root_count": root_count,
        "edge_count": edge_count,
        "session_root_found": session_root_found,
        "unresolved_parent_count": len(unresolved_parent_ids),
    }
    return errors, metrics


async def run_smoke(prompt: str, model: str, endpoint: str, home_dir: Path) -> dict:
    options = ClaudeAgentOptions(
        model=model,
        cwd=str(REPO_ROOT),
        max_turns=2,
        permission_mode="bypassPermissions",
        plugins=[{"type": "local", "path": str(PLUGIN_PATH)}],
        env={
            "HOME": str(home_dir),
            "ANTHROPIC_API_KEY": os.environ["ANTHROPIC_API_KEY"],
            "TRACE_TO_PROMPTLAYER": "true",
            "PROMPTLAYER_API_KEY": "pl_smoke_test_key",
            "PROMPTLAYER_OTLP_ENDPOINT": endpoint,
            "PROMPTLAYER_CC_DEBUG": "true",
            "PROMPTLAYER_QUEUE_DRAIN_LIMIT": "10",
        },
    )

    result = {"is_error": None, "result": ""}
    async with ClaudeSDKClient(options=options) as client:
        await client.query(prompt)
        async for message in client.receive_response():
            if type(message).__name__ == "ResultMessage":
                result["is_error"] = bool(getattr(message, "is_error", False))
                result["result"] = str(getattr(message, "result", ""))
    return result


def main() -> int:
    if not PLUGIN_PATH.exists():
        print(f"Plugin path not found: {PLUGIN_PATH}", file=sys.stderr)
        return 1
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is required for smoke test", file=sys.stderr)
        return 2

    model = "claude-3-haiku-20240307"
    run_id = f"pl-smoke-{int(time.time())}"
    prompt = (
        f"Reply with exactly: {run_id}\n"
        "Do not call tools. Do not add extra words or punctuation."
    )

    started_at = time.time()

    with tempfile.TemporaryDirectory(prefix="pl-smoke-home-") as tmp_home:
        home_dir = Path(tmp_home)
        state_dir = home_dir / ".claude" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        log_file = state_dir / "promptlayer_hook.log"

        with local_otlp_collector() as (endpoint, collected_payloads):
            try:
                result = asyncio.run(run_smoke(prompt, model, endpoint, home_dir))
            except Exception as exc:  # noqa: BLE001 - smoke test should report all runtime failures.
                print(f"Smoke run failed: {exc}", file=sys.stderr)
                return 1

            log_text, payloads = wait_for_hook_outputs(log_file, collected_payloads)

        hook_markers = (
            "SessionStart captured",
            "Session initialized lazily",
            "UserPromptSubmit captured",
            "PostToolUse captured",
            "Stop finalized",
            "SessionEnd finalized",
        )
        saw_hook = any(marker in log_text for marker in hook_markers)

        parsed_payloads, payload_schema_matches, spans = parse_otlp_spans(payloads)
        graph_errors, graph_metrics = validate_span_graph(spans)

        summary = {
            "model": model,
            "run_id": run_id,
            "agent_error": result.get("is_error"),
            "hook_seen": saw_hook,
            "payloads_received": len(payloads),
            "payloads_json_parsed": parsed_payloads,
            "payloads_schema_matched": payload_schema_matches,
            "graph_metrics": graph_metrics,
            "graph_errors": graph_errors,
            "log_file": str(log_file),
            "duration_s": round(time.time() - started_at, 2),
        }
    print(json.dumps(summary, indent=2))

    if result.get("is_error") is True:
        return 1
    if not saw_hook:
        return 1
    if summary["payloads_schema_matched"] <= 0:
        return 1
    if summary["graph_errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
