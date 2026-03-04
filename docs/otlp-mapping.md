# OTLP mapping

Initial mapping scaffold:

- SessionStart -> root/task span
- UserPromptSubmit -> in-flight turn timing state
- PostToolUse -> tool span (child of session root)
- Stop -> llm span (child of session root)
- SessionEnd -> terminal task span

All spans are sent via OTLP/HTTP JSON `ExportTraceServiceRequest`.
