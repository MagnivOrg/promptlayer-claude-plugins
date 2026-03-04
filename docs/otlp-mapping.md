# OTLP mapping

Initial mapping scaffold:

- SessionStart -> root/task span
- UserPromptSubmit -> turn/task span
- PostToolUse -> tool span
- Stop -> llm span
- SessionEnd -> terminal task span

All spans are sent via OTLP/HTTP JSON `ExportTraceServiceRequest`.
